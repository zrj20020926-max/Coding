from __future__ import annotations

# ruff: noqa: UP045
import hashlib
import json
import stat
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.problem import TestCase, TestGroup, TestSetStatus
from app.models.submission import Submission
from app.schemas.test_set import TestCaseBatchUploadPublic
from app.services.object_storage import SourceObjectStore
from app.services.test_sets import get_test_set, test_set_error, to_test_set_public


class ArchiveCase(BaseModel):
    sequence: int = Field(ge=0)
    score: Decimal = Field(gt=0, le=100, decimal_places=2)
    input: str = Field(min_length=1, max_length=500)
    output: str = Field(min_length=1, max_length=500)
    checksum: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("input", "output")
    @classmethod
    def safe_member_path(cls, value: str) -> str:
        path = PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ValueError("archive member path is unsafe")
        return path.as_posix()


class ArchiveManifest(BaseModel):
    cases: list[ArchiveCase] = Field(min_length=1, max_length=1000)

    @field_validator("cases")
    @classmethod
    def unique_sequences(cls, value: list[ArchiveCase]) -> list[ArchiveCase]:
        sequences = [item.sequence for item in value]
        if len(sequences) != len(set(sequences)):
            raise ValueError("case sequences must be unique")
        if sum((item.score for item in value), Decimal("0")) != Decimal("100"):
            raise ValueError("case scores must total 100")
        return value


@dataclass(frozen=True)
class PreparedCase:
    sequence: int
    score: Decimal
    input_data: bytes
    output_data: bytes
    checksum: str


def _safe_zip_member(info: zipfile.ZipInfo) -> None:
    path = PurePosixPath(info.filename.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("unsafe archive member")
    unix_mode = info.external_attr >> 16
    if unix_mode and stat.S_ISLNK(unix_mode):
        raise ValueError("symbolic links are forbidden")
    if info.flag_bits & 0x1:
        raise ValueError("encrypted archive members are forbidden")
    if info.file_size > settings.test_data_object_max_bytes:
        raise ValueError("archive member is too large")
    if info.compress_size == 0 and info.file_size > 0:
        raise ValueError("suspicious compression ratio")
    if (
        info.compress_size
        and info.file_size / info.compress_size > settings.test_data_archive_max_ratio
    ):
        raise ValueError("suspicious compression ratio")


def parse_test_data_archive(content: bytes) -> list[PreparedCase]:
    if len(content) > settings.test_data_archive_max_bytes:
        raise ValueError("archive is too large")
    try:
        archive = zipfile.ZipFile(BytesIO(content))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("invalid ZIP archive") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > settings.test_data_archive_max_files:
            raise ValueError("archive contains too many files")
        names: set[str] = set()
        total_size = 0
        for info in infos:
            _safe_zip_member(info)
            normalized = PurePosixPath(info.filename.replace("\\", "/")).as_posix()
            if normalized in names:
                raise ValueError("archive contains duplicate paths")
            names.add(normalized)
            total_size += info.file_size
        if total_size > settings.test_data_archive_uncompressed_max_bytes:
            raise ValueError("archive uncompressed content is too large")
        if "manifest.json" not in names:
            raise ValueError("archive must contain manifest.json")
        try:
            raw_manifest = archive.read("manifest.json").decode("utf-8")
            manifest_value: Any = json.loads(raw_manifest)
            manifest = ArchiveManifest.model_validate(manifest_value)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            raise ValueError("invalid UTF-8 archive manifest") from exc
        prepared: list[PreparedCase] = []
        for item in manifest.cases:
            if item.input not in names or item.output not in names:
                raise ValueError("manifest references a missing file")
            input_data = archive.read(item.input)
            output_data = archive.read(item.output)
            try:
                input_data.decode("utf-8")
                output_data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("test data must be valid UTF-8 text") from exc
            checksum = hashlib.sha256(input_data + b"\0" + output_data).hexdigest()
            if item.checksum is not None and item.checksum != checksum:
                raise ValueError("test data checksum mismatch")
            prepared.append(
                PreparedCase(item.sequence, item.score, input_data, output_data, checksum)
            )
        return prepared


async def upload_test_case_archive(
    db: AsyncSession,
    test_set_id: UUID,
    archive: bytes,
    object_store: SourceObjectStore,
) -> TestCaseBatchUploadPublic:
    try:
        prepared = parse_test_data_archive(archive)
    except (ValueError, InvalidOperation) as exc:
        raise test_set_error(422, "UNSAFE_TEST_DATA_ARCHIVE", str(exc)) from None
    test_set = await get_test_set(db, test_set_id, lock=True)
    if test_set is None:
        raise test_set_error(404, "TEST_SET_NOT_FOUND", "测试集不存在")
    referenced = await db.scalar(
        select(func.count(Submission.id)).where(Submission.test_set_id == test_set_id)
    )
    if referenced or test_set.status not in {TestSetStatus.DRAFT, TestSetStatus.INVALID}:
        raise test_set_error(409, "TEST_SET_IMMUTABLE", "已引用或非草稿测试集不可修改")
    if test_set.cases:
        raise test_set_error(409, "TEST_SET_NOT_EMPTY", "批量上传仅支持空测试集")

    batch_id = uuid4()
    uploaded: list[str] = []
    cases: list[TestCase] = []
    try:
        for item in prepared:
            prefix = f"test-sets/{test_set_id}/{batch_id}/{item.sequence}"
            input_key = f"{prefix}.in"
            output_key = f"{prefix}.out"
            await object_store.put_test_data(input_key, item.input_data)
            uploaded.append(input_key)
            await object_store.put_test_data(output_key, item.output_data)
            uploaded.append(output_key)
            group = TestGroup(
                test_set_id=test_set_id,
                name=f"case-{item.sequence}",
                sequence=item.sequence,
                score=item.score,
                short_circuit=True,
            )
            case = TestCase(
                    test_set_id=test_set_id,
                    sequence=item.sequence,
                    score=item.score,
                    input_object_key=input_key,
                    output_object_key=output_key,
                    checksum=item.checksum,
                    input_size_bytes=len(item.input_data),
                    output_size_bytes=len(item.output_data),
                    group=group,
            )
            cases.append(case)
        db.add_all(cases)
        test_set.case_count = len(cases)
        test_set.total_score = sum((item.score for item in prepared), Decimal("0"))
        test_set.status = TestSetStatus.DRAFT
        await db.commit()
    except (Exception, IntegrityError):
        await db.rollback()
        for object_key in reversed(uploaded):
            try:
                await object_store.delete_test_data(object_key)
            except Exception:
                pass
        raise test_set_error(503, "TEST_DATA_UPLOAD_FAILED", "测试数据未完整保存") from None
    loaded = await get_test_set(db, test_set_id)
    assert loaded is not None
    return TestCaseBatchUploadPublic(
        test_set=to_test_set_public(loaded), uploaded_count=len(prepared)
    )
