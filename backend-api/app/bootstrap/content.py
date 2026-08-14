# ruff: noqa: UP045
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, Optional, Union
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models.content import Collection, CollectionProblem, DailyChallenge
from app.models.problem import (
    CheckerType,
    Language,
    Problem,
    ProblemDifficulty,
    ProblemTag,
    ProblemVisibility,
    Tag,
    TestCase,
    TestGroup,
    TestSet,
    TestSetStatus,
    TrainingCategory,
)
from app.services.object_storage import SourceObjectStore, get_source_object_store
from app.services.test_sets import validate_test_set

CONTENT_LOCK_KEY = "codearena-content-bootstrap-v1"
MAX_CONTENT_FILE_BYTES = 1_048_576


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _safe_relative_path(value: str) -> str:
    candidate = Path(value)
    if not value or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("path must be a non-empty relative path without '..'")
    return candidate.as_posix()


class ContentManifest(StrictModel):
    schema_version: Literal[1]
    timezone: str = "Asia/Shanghai"
    tags: str
    problems: list[str] = Field(min_length=1)
    collections: str
    daily_challenges: str
    test_data_directory: str = "test-data"

    @field_validator("tags", "collections", "daily_challenges", "test_data_directory")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _safe_relative_path(value)

    @field_validator("problems")
    @classmethod
    def validate_problem_paths(cls, value: list[str]) -> list[str]:
        paths = [_safe_relative_path(item) for item in value]
        if len(paths) != len(set(paths)):
            raise ValueError("problem file paths must be unique")
        return paths

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value


class ContentTag(StrictModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=50)
    name: str = Field(min_length=1, max_length=50)


class TagsDocument(StrictModel):
    tags: list[ContentTag] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_tags(self) -> TagsDocument:
        slugs = [item.slug for item in self.tags]
        names = [item.name for item in self.tags]
        if len(slugs) != len(set(slugs)) or len(names) != len(set(names)):
            raise ValueError("tag slugs and names must be unique")
        return self


class HiddenCaseContent(StrictModel):
    sequence: int = Field(ge=0)
    score: Decimal = Field(gt=0, le=100, decimal_places=2)
    input_file: str
    output_file: str
    checksum: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    scenario: Literal[
        "minimum_boundary",
        "normal",
        "duplicates",
        "special_structure",
        "performance",
        "counterexample",
    ]
    scenario_description: str = Field(min_length=1, max_length=500)

    @field_validator("input_file", "output_file")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        return _safe_relative_path(value)


class TestSetContent(StrictModel):
    version: int = Field(ge=1)
    checker_type: CheckerType = CheckerType.EXACT
    absolute_tolerance: Optional[Decimal] = Field(default=None, ge=0)
    relative_tolerance: Optional[Decimal] = Field(default=None, ge=0)
    cases: list[HiddenCaseContent] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_test_set(self) -> TestSetContent:
        sequences = [item.sequence for item in self.cases]
        if len(sequences) != len(set(sequences)):
            raise ValueError("test case sequences must be unique")
        if sum((item.score for item in self.cases), Decimal("0")) != Decimal("100"):
            raise ValueError("test case scores must total 100")
        required_scenarios = {
            "minimum_boundary",
            "normal",
            "duplicates",
            "special_structure",
            "performance",
            "counterexample",
        }
        if not required_scenarios <= {item.scenario for item in self.cases}:
            raise ValueError("test cases must cover all six required scenario categories")
        if self.checker_type is CheckerType.FLOAT:
            if self.absolute_tolerance is None or self.relative_tolerance is None:
                raise ValueError("float checker requires both tolerances")
            if self.absolute_tolerance == 0 and self.relative_tolerance == 0:
                raise ValueError("float checker requires a positive tolerance")
        elif self.absolute_tolerance is not None or self.relative_tolerance is not None:
            raise ValueError("exact/token checker does not accept tolerances")
        return self


class ReferenceSolutions(StrictModel):
    python: str
    cpp: str

    @field_validator("python", "cpp")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _safe_relative_path(value)


class ProblemContent(StrictModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=100_000)
    difficulty: ProblemDifficulty
    training_category: Optional[TrainingCategory] = None
    tags: list[str] = Field(min_length=1, max_length=30)
    input_description: str = Field(min_length=1, max_length=20_000)
    output_description: str = Field(min_length=1, max_length=20_000)
    data_constraints: str = Field(min_length=1, max_length=20_000)
    sample_input: str = Field(max_length=100_000)
    sample_output: str = Field(max_length=100_000)
    sample_explanation: str = Field(min_length=1, max_length=20_000)
    starter_code_v8: Optional[str] = Field(default=None, max_length=262_144)
    starter_code_nodejs: Optional[str] = Field(default=None, max_length=262_144)
    time_limit_ms: int = Field(default=1000, ge=100, le=30_000)
    memory_limit_mb: int = Field(default=256, ge=16, le=2048)
    source: Optional[str] = Field(default=None, max_length=200)
    publish: bool = True
    reference_solutions: ReferenceSolutions
    test_set: TestSetContent

    @field_validator("tags")
    @classmethod
    def validate_unique_tags(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("problem tags must be unique")
        return value


class CollectionContent(StrictModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=10_000)
    company: Optional[str] = Field(default=None, max_length=50)
    cover_url: Optional[str] = Field(default=None, max_length=2_000)
    is_public: bool = True
    problems: list[str] = Field(min_length=1, max_length=500)

    @field_validator("problems")
    @classmethod
    def validate_unique_problems(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("collection problems must be unique")
        return value


class CollectionsDocument(StrictModel):
    collections: list[CollectionContent] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_collections(self) -> CollectionsDocument:
        slugs = [item.slug for item in self.collections]
        if len(slugs) != len(set(slugs)):
            raise ValueError("collection slugs must be unique")
        return self


class DailyChallengeContent(StrictModel):
    date: Union[Date, str]
    problem: str

    @field_validator("date")
    @classmethod
    def validate_relative_date(cls, value: Date | str) -> Date | str:
        if isinstance(value, Date):
            return value
        if value == "today":
            return value
        if value.startswith("today+") and value[6:].isdigit() and 1 <= int(value[6:]) <= 365:
            return value
        raise ValueError("date must be an ISO date, today, or today+N (1-365)")


class DailyChallengesDocument(StrictModel):
    daily_challenges: list[DailyChallengeContent] = Field(min_length=1)


class EntityReport(StrictModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0


class ContentImportReport(StrictModel):
    status: Literal["success", "validated", "dry-run", "disabled", "failed"]
    dry_run: bool = False
    validate_only: bool = False
    tags: EntityReport = Field(default_factory=EntityReport)
    problems: EntityReport = Field(default_factory=EntityReport)
    test_sets: EntityReport = Field(default_factory=EntityReport)
    test_cases: EntityReport = Field(default_factory=EntityReport)
    objects: EntityReport = Field(default_factory=EntityReport)
    collections: EntityReport = Field(default_factory=EntityReport)
    daily_challenges: EntityReport = Field(default_factory=EntityReport)
    failures: int = 0
    cleanup_failures: int = 0


class ContentBootstrapError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        cleanup_failures: int = 0,
        report: ContentImportReport | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.cleanup_failures = cleanup_failures
        self.report = report


@dataclass(frozen=True)
class MaterializedCase:
    sequence: int
    score: Decimal
    input_data: bytes
    output_data: bytes
    input_hash: str
    output_hash: str
    checksum: str
    input_object_key: str
    output_object_key: str


@dataclass(frozen=True)
class MaterializedProblem:
    document: ProblemContent
    cases: tuple[MaterializedCase, ...]
    test_set_digest: str


@dataclass(frozen=True)
class ContentBundle:
    manifest: ContentManifest
    tags: tuple[ContentTag, ...]
    problems: dict[str, MaterializedProblem]
    collections: tuple[CollectionContent, ...]
    daily_challenges: tuple[DailyChallengeContent, ...]


def _load_yaml(path: Path, model: type[StrictModel], label: str) -> StrictModel:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return model.model_validate(raw)
    except (OSError, UnicodeError, yaml.YAMLError, ValidationError, ValueError) as exc:
        raise ContentBootstrapError("CONTENT_INVALID", f"{label}格式或路径无效") from exc


def _resolve_inside(root: Path, relative: str, label: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        raise ContentBootstrapError("CONTENT_INVALID", f"{label}路径越界") from None
    return candidate


def _read_hidden_file(path: Path, label: str) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ContentBootstrapError("CONTENT_INVALID", f"{label}不可读取") from exc
    if len(data) > settings.test_data_object_max_bytes:
        raise ContentBootstrapError("CONTENT_INVALID", f"{label}超过大小限制")
    return data


def _materialize_problem(
    document: ProblemContent, test_data_root: Path, content_root: Path
) -> MaterializedProblem:
    for language, relative in (
        ("Python", document.reference_solutions.python),
        ("C++", document.reference_solutions.cpp),
    ):
        reference_path = _resolve_inside(content_root, relative, f"{language} 引用实现")
        try:
            reference_source = reference_path.read_bytes()
        except OSError as exc:
            raise ContentBootstrapError(
                "CONTENT_INVALID", f"题目 {document.slug} 的 {language} 引用实现不可读取"
            ) from exc
        if not reference_source or len(reference_source) > MAX_CONTENT_FILE_BYTES:
            raise ContentBootstrapError(
                "CONTENT_INVALID", f"题目 {document.slug} 的 {language} 引用实现大小无效"
            )
    cases: list[MaterializedCase] = []
    digest_parts: list[str] = [
        document.test_set.checker_type.value,
        str(document.test_set.absolute_tolerance),
        str(document.test_set.relative_tolerance),
    ]
    staged: list[tuple[HiddenCaseContent, bytes, bytes, str, str, str]] = []
    for case in sorted(document.test_set.cases, key=lambda item: item.sequence):
        input_data = _read_hidden_file(
            _resolve_inside(test_data_root, case.input_file, "隐藏输入"), "隐藏输入"
        )
        output_data = _read_hidden_file(
            _resolve_inside(test_data_root, case.output_file, "隐藏输出"), "隐藏输出"
        )
        input_hash = hashlib.sha256(input_data).hexdigest()
        output_hash = hashlib.sha256(output_data).hexdigest()
        checksum = hashlib.sha256(input_data + b"\0" + output_data).hexdigest()
        if case.checksum is not None and case.checksum != checksum:
            raise ContentBootstrapError(
                "CHECKSUM_MISMATCH",
                f"题目 {document.slug} 的隐藏用例 {case.sequence} 校验失败",
            )
        digest_parts.extend(
            [str(case.sequence), str(case.score), input_hash, output_hash, checksum]
        )
        staged.append((case, input_data, output_data, input_hash, output_hash, checksum))
    digest = hashlib.sha256("|".join(digest_parts).encode()).hexdigest()
    for case, input_data, output_data, input_hash, output_hash, checksum in staged:
        prefix = f"content/{document.slug}/{digest}/{case.sequence:04d}"
        cases.append(
            MaterializedCase(
                sequence=case.sequence,
                score=case.score,
                input_data=input_data,
                output_data=output_data,
                input_hash=input_hash,
                output_hash=output_hash,
                checksum=checksum,
                input_object_key=f"{prefix}/input-{input_hash}",
                output_object_key=f"{prefix}/output-{output_hash}",
            )
        )
    return MaterializedProblem(document=document, cases=tuple(cases), test_set_digest=digest)


def load_content_bundle(
    manifest_path: Path,
    problem_slug: str | None = None,
    collection_slug: str | None = None,
) -> ContentBundle:
    manifest_path = manifest_path.resolve()
    manifest = _load_yaml(manifest_path, ContentManifest, "manifest")
    assert isinstance(manifest, ContentManifest)
    root = manifest_path.parent
    tags_doc = _load_yaml(
        _resolve_inside(root, manifest.tags, "标签文件"), TagsDocument, "标签文件"
    )
    collections_doc = _load_yaml(
        _resolve_inside(root, manifest.collections, "题单文件"),
        CollectionsDocument,
        "题单文件",
    )
    daily_doc = _load_yaml(
        _resolve_inside(root, manifest.daily_challenges, "每日一题文件"),
        DailyChallengesDocument,
        "每日一题文件",
    )
    assert isinstance(tags_doc, TagsDocument)
    assert isinstance(collections_doc, CollectionsDocument)
    assert isinstance(daily_doc, DailyChallengesDocument)

    selected_collections = tuple(
        item
        for item in collections_doc.collections
        if collection_slug is None or item.slug == collection_slug
    )
    if collection_slug is not None and not selected_collections:
        raise ContentBootstrapError("CONTENT_NOT_FOUND", "指定题单不在 manifest 中")
    required_problem_slugs = (
        set(selected_collections[0].problems) if collection_slug is not None else None
    )
    if problem_slug is not None:
        required_problem_slugs = {problem_slug}

    test_data_root = _resolve_inside(root, manifest.test_data_directory, "测试数据目录")
    problems: dict[str, MaterializedProblem] = {}
    all_problem_slugs: set[str] = set()
    for relative in manifest.problems:
        document = _load_yaml(
            _resolve_inside(root, relative, "题目文件"), ProblemContent, "题目文件"
        )
        assert isinstance(document, ProblemContent)
        if document.slug in all_problem_slugs:
            raise ContentBootstrapError("CONTENT_INVALID", "题目 slug 重复")
        all_problem_slugs.add(document.slug)
        if required_problem_slugs is None or document.slug in required_problem_slugs:
            problems[document.slug] = _materialize_problem(document, test_data_root, root)
    if required_problem_slugs is not None and set(problems) != required_problem_slugs:
        raise ContentBootstrapError("CONTENT_NOT_FOUND", "指定内容引用了不存在的题目")

    tag_slugs = {item.slug for item in tags_doc.tags}
    for materialized in problems.values():
        if not set(materialized.document.tags) <= tag_slugs:
            raise ContentBootstrapError("CONTENT_INVALID", "题目引用了不存在的标签")
    referenced = {
        slug for collection in selected_collections for slug in collection.problems
    }
    if not referenced <= all_problem_slugs:
        raise ContentBootstrapError("CONTENT_INVALID", "题单引用了不存在的题目")
    daily = (
        tuple(daily_doc.daily_challenges)
        if problem_slug is None and collection_slug is None
        else ()
    )
    if not {item.problem for item in daily} <= all_problem_slugs:
        raise ContentBootstrapError("CONTENT_INVALID", "每日一题引用了不存在的题目")
    effective_dates = [_challenge_date(item, manifest.timezone) for item in daily]
    if len(effective_dates) != len(set(effective_dates)):
        raise ContentBootstrapError("CONTENT_INVALID", "每日一题日期重复")
    if manifest.timezone != settings.content_timezone:
        raise ContentBootstrapError("TIMEZONE_MISMATCH", "manifest 时区与服务端配置不一致")
    return ContentBundle(
        manifest=manifest,
        tags=tuple(tags_doc.tags),
        problems=problems,
        collections=selected_collections if problem_slug is None else (),
        daily_challenges=daily,
    )


def _problem_values(document: ProblemContent) -> dict[str, object]:
    values: dict[str, object] = {
        "title": document.title,
        "description": document.description,
        "difficulty": document.difficulty,
        "input_description": document.input_description,
        "output_description": document.output_description,
        "data_constraints": document.data_constraints,
        "sample_input": document.sample_input,
        "sample_output": document.sample_output,
        "sample_explanation": document.sample_explanation,
        "time_limit_ms": document.time_limit_ms,
        "memory_limit_mb": document.memory_limit_mb,
        "source": document.source,
    }
    if document.training_category is not None:
        values["training_category"] = document.training_category
    if document.starter_code_v8 is not None:
        values["starter_code_v8"] = document.starter_code_v8
    if document.starter_code_nodejs is not None:
        values["starter_code_nodejs"] = document.starter_code_nodejs
    return values


def _challenge_date(item: DailyChallengeContent, timezone: str) -> Date:
    if isinstance(item.date, Date):
        return item.date
    today = datetime.now(ZoneInfo(timezone)).date()
    if item.date == "today":
        return today
    return today + timedelta(days=int(item.date[6:]))


def _test_set_matches(test_set: TestSet, desired: MaterializedProblem) -> bool:
    config = desired.document.test_set
    if (
        test_set.checker_type is not config.checker_type
        or test_set.absolute_tolerance != config.absolute_tolerance
        or test_set.relative_tolerance != config.relative_tolerance
        or len(test_set.cases) != len(desired.cases)
    ):
        return False
    actual = sorted(test_set.cases, key=lambda item: item.sequence)
    return all(
        row.sequence == case.sequence
        and row.score == case.score
        and row.checksum == case.checksum
        and row.input_object_key == case.input_object_key
        and row.output_object_key == case.output_object_key
        and row.input_size_bytes == len(case.input_data)
        and row.output_size_bytes == len(case.output_data)
        for row, case in zip(actual, desired.cases)
    )


async def _ensure_test_object(
    store: SourceObjectStore,
    object_key: str,
    content: bytes,
    expected_hash: str,
    uploaded: list[str],
    report: EntityReport,
    dry_run: bool,
) -> None:
    try:
        exists = await store.test_data_exists(object_key)
        if exists:
            stored = await store.get_test_data(object_key)
            if hashlib.sha256(stored).hexdigest() != expected_hash:
                raise ContentBootstrapError(
                    "STORED_OBJECT_CORRUPT", "已存在的测试数据对象校验失败"
                )
            report.skipped += 1
            return
        if dry_run:
            report.created += 1
            return
        await store.put_test_data(object_key, content)
        uploaded.append(object_key)
        report.created += 1
    except ContentBootstrapError:
        raise
    except Exception as exc:
        raise ContentBootstrapError(
            "TEST_DATA_STORAGE_FAILED", "测试数据存储暂时不可用"
        ) from exc


async def _cleanup_objects(
    db: AsyncSession, store: SourceObjectStore, uploaded: list[str]
) -> int:
    failures = 0
    for object_key in reversed(uploaded):
        try:
            referenced = await db.scalar(
                select(func.count(TestCase.id)).where(
                    (TestCase.input_object_key == object_key)
                    | (TestCase.output_object_key == object_key)
                )
            )
            if referenced:
                continue
            await store.delete_test_data(object_key)
        except Exception:
            # An unavailable database makes commit outcome ambiguous. Retaining an
            # unverified object is safer than deleting data a committed row may reference.
            failures += 1
    return failures


async def _lock_content_import(db: AsyncSession) -> None:
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": CONTENT_LOCK_KEY},
        )


async def _ensure_languages(db: AsyncSession) -> None:
    slugs = set(
        (
            await db.scalars(
                select(Language.slug).where(
                    Language.enabled.is_(True),
                    Language.slug.in_(["javascript-v8", "nodejs"]),
                )
            )
        ).all()
    )
    if slugs != {"javascript-v8", "nodejs"}:
        raise ContentBootstrapError(
            "LANGUAGE_UNAVAILABLE", "内容发布要求 JavaScript V8 和 Node.js 判题模式"
        )


async def import_content_bundle(
    db: AsyncSession,
    store: SourceObjectStore,
    bundle: ContentBundle,
    *,
    dry_run: bool = False,
    allow_published_updates: bool = False,
) -> ContentImportReport:
    report = ContentImportReport(status="dry-run" if dry_run else "success", dry_run=dry_run)
    uploaded: list[str] = []
    try:
        await _lock_content_import(db)
        await _ensure_languages(db)
        tags = {item.slug: item for item in (await db.scalars(select(Tag))).all()}
        for desired in bundle.tags:
            existing = tags.get(desired.slug)
            if existing is None:
                report.tags.created += 1
                if not dry_run:
                    existing = Tag(slug=desired.slug, name=desired.name)
                    db.add(existing)
                    tags[desired.slug] = existing
            elif existing.name != desired.name:
                if settings.app_env.lower() == "production" and not allow_published_updates:
                    raise ContentBootstrapError(
                        "PUBLISHED_CONTENT_PROTECTED",
                        "生产环境禁止自动覆盖已有标签",
                    )
                report.tags.updated += 1
                if not dry_run:
                    existing.name = desired.name
            else:
                report.tags.skipped += 1
        if not dry_run:
            await db.flush()

        problems = {
            item.slug: item
            for item in (
                await db.scalars(
                    select(Problem).options(
                        selectinload(Problem.tag_links).selectinload(ProblemTag.tag),
                        selectinload(Problem.test_sets).selectinload(TestSet.cases),
                    ).execution_options(populate_existing=True)
                )
            ).unique().all()
        }
        resolved: dict[str, Problem] = {}
        for slug, desired in bundle.problems.items():
            document = desired.document
            problem = problems.get(slug)
            values = _problem_values(document)
            if problem is None:
                report.problems.created += 1
                if dry_run:
                    report.test_sets.created += 1
                    report.test_cases.created += len(desired.cases)
                    for case in desired.cases:
                        await _ensure_test_object(
                            store,
                            case.input_object_key,
                            case.input_data,
                            case.input_hash,
                            uploaded,
                            report.objects,
                            True,
                        )
                        await _ensure_test_object(
                            store,
                            case.output_object_key,
                            case.output_data,
                            case.output_hash,
                            uploaded,
                            report.objects,
                            True,
                        )
                    continue
                problem = Problem(
                    slug=slug,
                    visibility=ProblemVisibility.DRAFT,
                    tag_links=[],
                    test_sets=[],
                    **values,
                )
                db.add(problem)
                problems[slug] = problem
                await db.flush()
            else:
                statement_changed = any(
                    getattr(problem, key) != value for key, value in values.items()
                )
                desired_tags = set(document.tags)
                actual_tags = {link.tag.slug for link in problem.tag_links}
                changed = statement_changed or desired_tags != actual_tags
                if changed:
                    if (
                        settings.app_env.lower() == "production"
                        and problem.visibility is ProblemVisibility.PUBLIC
                        and not allow_published_updates
                    ):
                        raise ContentBootstrapError(
                            "PUBLISHED_CONTENT_PROTECTED",
                            "生产环境禁止自动覆盖已发布题目",
                        )
                    report.problems.updated += 1
                    if not dry_run:
                        if statement_changed:
                            problem.version += 1
                        for key, value in values.items():
                            setattr(problem, key, value)
                else:
                    report.problems.skipped += 1
            if dry_run:
                active = next(
                    (
                        item
                        for item in problem.test_sets
                            if item.status == TestSetStatus.ACTIVE
                    ),
                    None,
                )
                if active is not None and _test_set_matches(active, desired):
                    report.test_sets.skipped += 1
                    report.test_cases.skipped += len(desired.cases)
                else:
                    report.test_sets.created += 1
                    report.test_cases.created += len(desired.cases)
                for case in desired.cases:
                    await _ensure_test_object(
                        store,
                        case.input_object_key,
                        case.input_data,
                        case.input_hash,
                        uploaded,
                        report.objects,
                        True,
                    )
                    await _ensure_test_object(
                        store,
                        case.output_object_key,
                        case.output_data,
                        case.output_hash,
                        uploaded,
                        report.objects,
                        True,
                    )
                continue

            problem.tag_links = [
                ProblemTag(tag_id=tags[tag_slug].id) for tag_slug in document.tags
            ]
            await db.flush()
            resolved[slug] = problem
            active = next(
                (
                        item
                        for item in problem.test_sets
                        if item.status == TestSetStatus.ACTIVE
                ),
                None,
            )
            for case in desired.cases:
                await _ensure_test_object(
                    store,
                    case.input_object_key,
                    case.input_data,
                    case.input_hash,
                    uploaded,
                    report.objects,
                    False,
                )
                await _ensure_test_object(
                    store,
                    case.output_object_key,
                    case.output_data,
                    case.output_hash,
                    uploaded,
                    report.objects,
                    False,
                )
            if active is not None and _test_set_matches(active, desired):
                issues = await validate_test_set(db, active, store)
                if issues:
                    raise ContentBootstrapError(
                        "ACTIVE_TEST_SET_INVALID", "活动测试集未通过完整性校验"
                    )
                report.test_sets.skipped += 1
                report.test_cases.skipped += len(desired.cases)
            else:
                if (
                    problem.visibility is ProblemVisibility.PUBLIC
                    and settings.app_env.lower() == "production"
                    and not allow_published_updates
                ):
                    raise ContentBootstrapError(
                        "PUBLISHED_CONTENT_PROTECTED",
                        "生产环境禁止自动替换已发布题目的活动测试集",
                    )
                next_version = (
                    await db.scalar(
                        select(func.coalesce(func.max(TestSet.version), 0) + 1).where(
                            TestSet.problem_id == problem.id
                        )
                    )
                )
                config = document.test_set
                next_version = max(next_version, config.version)
                new_set = TestSet(
                    problem_id=problem.id,
                    version=next_version,
                    status=TestSetStatus.DRAFT,
                    checker_type=config.checker_type,
                    absolute_tolerance=config.absolute_tolerance,
                    relative_tolerance=config.relative_tolerance,
                    case_count=len(desired.cases),
                    total_score=Decimal("100"),
                )
                for case in desired.cases:
                    group = TestGroup(
                        name=f"case-{case.sequence}",
                        sequence=case.sequence,
                        score=case.score,
                        short_circuit=True,
                    )
                    group.cases.append(
                        TestCase(
                            sequence=case.sequence,
                            score=case.score,
                            input_object_key=case.input_object_key,
                            output_object_key=case.output_object_key,
                            checksum=case.checksum,
                            input_size_bytes=len(case.input_data),
                            output_size_bytes=len(case.output_data),
                        )
                    )
                    new_set.groups.append(group)
                db.add(new_set)
                await db.flush()
                await db.refresh(new_set, attribute_names=["cases", "groups"])
                new_set.status = TestSetStatus.VALIDATING
                await db.flush()
                issues = await validate_test_set(db, new_set, store)
                if issues:
                    raise ContentBootstrapError(
                        "TEST_SET_INVALID", "新测试集未通过完整性校验"
                    )
                new_set.status = TestSetStatus.READY
                await db.flush()
                if active is not None:
                    active.status = TestSetStatus.INACTIVE
                    await db.flush()
                new_set.status = TestSetStatus.ACTIVE
                new_set.activated_at = datetime.now(ZoneInfo("UTC"))
                report.test_sets.created += 1
                report.test_cases.created += len(desired.cases)
            problem.visibility = (
                ProblemVisibility.PUBLIC if document.publish else ProblemVisibility.DRAFT
            )

        if dry_run:
            existing_collections = {
                item.slug: item for item in (await db.scalars(select(Collection))).all()
            }
            for desired in bundle.collections:
                if desired.slug in existing_collections:
                    report.collections.updated += 1
                else:
                    report.collections.created += 1
            report.daily_challenges.updated += len(bundle.daily_challenges)
            await db.rollback()
            return report

        for desired in bundle.collections:
            collection = await db.scalar(
                select(Collection)
                .options(selectinload(Collection.items))
                .where(Collection.slug == desired.slug)
                .execution_options(populate_existing=True)
            )
            desired_ids = [resolved[slug].id for slug in desired.problems]
            if collection is None:
                collection = Collection(
                    slug=desired.slug,
                    title=desired.title,
                    description=desired.description,
                    company=desired.company,
                    cover_url=desired.cover_url,
                    is_public=desired.is_public,
                    items=[],
                )
                db.add(collection)
                report.collections.created += 1
                await db.flush()
                changed = True
            else:
                actual_ids = [item.problem_id for item in collection.items]
                changed = actual_ids != desired_ids or any(
                    getattr(collection, key) != value
                    for key, value in {
                        "title": desired.title,
                        "description": desired.description,
                        "company": desired.company,
                        "cover_url": desired.cover_url,
                        "is_public": desired.is_public,
                    }.items()
                )
                if changed:
                    if (
                        settings.app_env.lower() == "production"
                        and collection.is_public
                        and not allow_published_updates
                    ):
                        raise ContentBootstrapError(
                            "PUBLISHED_CONTENT_PROTECTED",
                            "生产环境禁止自动覆盖已发布题单",
                        )
                    report.collections.updated += 1
                else:
                    report.collections.skipped += 1
            collection.title = desired.title
            collection.description = desired.description
            collection.company = desired.company
            collection.cover_url = desired.cover_url
            collection.is_public = desired.is_public
            if changed:
                await db.execute(
                    delete(CollectionProblem).where(
                        CollectionProblem.collection_id == collection.id
                    )
                )
                collection.items = [
                    CollectionProblem(problem_id=problem_id, sequence=index)
                    for index, problem_id in enumerate(desired_ids, start=1)
                ]

        for desired in bundle.daily_challenges:
            challenge_date = _challenge_date(desired, bundle.manifest.timezone)
            problem = resolved.get(desired.problem) or problems.get(desired.problem)
            if problem is None or problem.visibility is not ProblemVisibility.PUBLIC:
                raise ContentBootstrapError(
                    "DAILY_CHALLENGE_INVALID", "每日一题必须引用已发布题目"
                )
            challenge = await db.get(DailyChallenge, challenge_date)
            if challenge is None:
                db.add(
                    DailyChallenge(
                        challenge_date=challenge_date, problem_id=problem.id
                    )
                )
                report.daily_challenges.created += 1
            elif challenge.problem_id != problem.id:
                if (
                    settings.app_env.lower() == "production"
                    and not allow_published_updates
                ):
                    raise ContentBootstrapError(
                        "PUBLISHED_CONTENT_PROTECTED",
                        "生产环境禁止自动替换已有每日一题",
                    )
                challenge.problem_id = problem.id
                report.daily_challenges.updated += 1
            else:
                report.daily_challenges.skipped += 1

        await db.commit()
        return report
    except Exception as exc:
        await db.rollback()
        cleanup_failures = await _cleanup_objects(db, store, uploaded)
        if isinstance(exc, ContentBootstrapError):
            exc.cleanup_failures += cleanup_failures
            report.status = "failed"
            report.failures += 1
            report.cleanup_failures = exc.cleanup_failures
            exc.report = report
            raise
        report.status = "failed"
        report.failures += 1
        report.cleanup_failures = cleanup_failures
        raise ContentBootstrapError(
            "CONTENT_IMPORT_FAILED", "内容导入事务失败", cleanup_failures, report
        ) from exc


async def run_content_bootstrap(
    manifest_path: Path,
    *,
    dry_run: bool = False,
    validate_only: bool = False,
    problem_slug: str | None = None,
    collection_slug: str | None = None,
    allow_published_updates: bool = False,
    db: AsyncSession | None = None,
    store: SourceObjectStore | None = None,
) -> ContentImportReport:
    bundle = load_content_bundle(manifest_path, problem_slug, collection_slug)
    if validate_only:
        return ContentImportReport(status="validated", validate_only=True)
    if (
        settings.app_env.lower() == "production"
        and allow_published_updates
        and os.getenv("CONTENT_ALLOW_PUBLISHED_UPDATES", "false").lower()
        not in {"1", "true", "yes", "on"}
    ):
        raise ContentBootstrapError(
            "PUBLISHED_UPDATE_NOT_AUTHORIZED",
            "生产覆盖需要显式启用 CONTENT_ALLOW_PUBLISHED_UPDATES",
        )
    owns_session = db is None
    session = db or SessionLocal()
    try:
        return await import_content_bundle(
            session,
            store or get_source_object_store(),
            bundle,
            dry_run=dry_run,
            allow_published_updates=allow_published_updates,
        )
    finally:
        if owns_session:
            await session.close()


def _failure_json(exc: ContentBootstrapError) -> str:
    report = exc.report or ContentImportReport(
        status="failed", failures=1, cleanup_failures=exc.cleanup_failures
    )
    payload = report.model_dump(mode="json")
    payload["error"] = {"code": exc.code, "message": exc.safe_message}
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


async def _async_main(args: argparse.Namespace) -> int:
    configured_auto_import = os.getenv("CONTENT_AUTO_IMPORT")
    auto_import_enabled = (
        settings.app_env.lower() != "production"
        if configured_auto_import is None or not configured_auto_import.strip()
        else configured_auto_import.lower() in {"1", "true", "yes", "on"}
    )
    if not args.force and not auto_import_enabled:
        print(ContentImportReport(status="disabled").model_dump_json())
        return 0
    try:
        report = await run_content_bootstrap(
            args.manifest,
            dry_run=args.dry_run,
            validate_only=args.validate_only,
            problem_slug=args.problem,
            collection_slug=args.collection,
            allow_published_updates=args.allow_published_updates,
        )
        print(report.model_dump_json())
        return 0
    except ContentBootstrapError as exc:
        print(_failure_json(exc), file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="幂等初始化 CodeArena 正式内容")
    parser.add_argument("--manifest", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--validate-only", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--problem")
    selection.add_argument("--collection")
    parser.add_argument("--allow-published-updates", action="store_true")
    parser.add_argument("--force", action="store_true", help="忽略 CONTENT_AUTO_IMPORT 开关")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_async_main(args)))


if __name__ == "__main__":
    main()
