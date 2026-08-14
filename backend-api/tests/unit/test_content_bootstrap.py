from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.content import (
    ContentBootstrapError,
    import_content_bundle,
    load_content_bundle,
    run_content_bootstrap,
)
from app.models.content import Collection, CollectionProblem, DailyChallenge
from app.models.problem import Language, Problem, ProblemVisibility
from app.models.problem import TestSet as ProblemTestSet
from app.models.problem import TestSetStatus as ProblemTestSetStatus
from tests.unit.conftest import FakeSourceObjectStore

CONTENT_ROOT = Path(__file__).resolve().parents[3] / "content"


async def seed_languages(db: AsyncSession) -> None:
    db.add_all(
        [
            Language(
                slug="javascript-v8",
                display_name="JavaScript V8",
                version="ES2023",
                monaco_language="javascript",
                source_filename="main.js",
                run_command="internal",
                docker_image="internal",
                enabled=True,
            ),
            Language(
                slug="nodejs",
                display_name="Node.js",
                version="22",
                monaco_language="javascript",
                source_filename="main.js",
                run_command="internal",
                docker_image="internal",
                enabled=True,
            ),
        ]
    )
    await db.commit()


def copy_content(tmp_path: Path) -> Path:
    destination = tmp_path / "content"
    shutil.copytree(CONTENT_ROOT, destination)
    return destination / "manifest.yaml"


@pytest.mark.unit
def test_manifest_is_strict_and_checksums_are_verified(tmp_path: Path) -> None:
    manifest = copy_content(tmp_path)
    raw = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    raw["unknown"] = True
    manifest.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ContentBootstrapError) as invalid:
        load_content_bundle(manifest)
    assert invalid.value.code == "CONTENT_INVALID"

    manifest = copy_content(tmp_path / "checksum")
    problem_path = (
        manifest.parent / "problems" / "js-acm" / "js-acm-read-one-integer.yaml"
    )
    problem = yaml.safe_load(problem_path.read_text(encoding="utf-8"))
    problem["test_set"]["cases"][0]["checksum"] = "0" * 64
    problem_path.write_text(
        yaml.safe_dump(problem, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    with pytest.raises(ContentBootstrapError) as mismatch:
        load_content_bundle(manifest)
    assert mismatch.value.code == "CHECKSUM_MISMATCH"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_only_and_dry_run_do_not_write(
    db_session: AsyncSession, fake_object_store: FakeSourceObjectStore
) -> None:
    await seed_languages(db_session)
    validated = await run_content_bootstrap(
        CONTENT_ROOT / "manifest.yaml",
        validate_only=True,
        db=db_session,
        store=fake_object_store,
    )
    assert validated.status == "validated"
    dry_run = await run_content_bootstrap(
        CONTENT_ROOT / "manifest.yaml",
        dry_run=True,
        db=db_session,
        store=fake_object_store,
    )
    assert dry_run.status == "dry-run"
    assert dry_run.problems.created == 168
    assert await db_session.scalar(select(func.count(Problem.id))) == 0
    assert fake_object_store.test_objects == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_bootstrap_is_idempotent_and_populates_all_content(
    db_session: AsyncSession, fake_object_store: FakeSourceObjectStore
) -> None:
    await seed_languages(db_session)
    first = await run_content_bootstrap(
        CONTENT_ROOT / "manifest.yaml", db=db_session, store=fake_object_store
    )
    second = await run_content_bootstrap(
        CONTENT_ROOT / "manifest.yaml", db=db_session, store=fake_object_store
    )
    assert first.problems.created == 168
    assert first.test_sets.created == 168
    assert second.problems.skipped == 168
    assert second.test_sets.skipped == 168
    assert second.collections.skipped == 18
    assert second.daily_challenges.skipped == 14
    assert await db_session.scalar(select(func.count(Problem.id))) == 168
    assert await db_session.scalar(select(func.count(ProblemTestSet.id))) == 168
    assert await db_session.scalar(select(func.count(Collection.id))) == 18
    assert await db_session.scalar(select(func.count(CollectionProblem.problem_id))) == 168
    assert await db_session.scalar(select(func.count(DailyChallenge.problem_id))) == 14
    challenge = await db_session.scalar(select(DailyChallenge))
    assert challenge is not None
    assert challenge.challenge_date == datetime.now(ZoneInfo("Asia/Shanghai")).date()
    assert len(fake_object_store.test_objects) == 2016
    public = (
        await db_session.scalars(
            select(Problem).where(Problem.visibility == ProblemVisibility.PUBLIC)
        )
    ).all()
    assert len(public) == 168
    for problem in public:
        active_count = await db_session.scalar(
            select(func.count(ProblemTestSet.id)).where(
                ProblemTestSet.problem_id == problem.id,
                ProblemTestSet.status == ProblemTestSetStatus.ACTIVE,
            )
        )
        assert active_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_single_problem_update_creates_version_only_when_test_content_changes(
    db_session: AsyncSession,
    fake_object_store: FakeSourceObjectStore,
    tmp_path: Path,
) -> None:
    await seed_languages(db_session)
    manifest = copy_content(tmp_path)
    await run_content_bootstrap(manifest, db=db_session, store=fake_object_store)
    unchanged = await run_content_bootstrap(
        manifest,
        problem_slug="js-acm-read-one-integer",
        db=db_session,
        store=fake_object_store,
    )
    assert unchanged.test_sets.skipped == 1

    hidden_output = (
        manifest.parent
        / "test-data"
        / "js-acm"
        / "js-acm-read-one-integer"
        / "01.out"
    )
    hidden_output.write_text("1\n", encoding="utf-8")
    problem_path = (
        manifest.parent / "problems" / "js-acm" / "js-acm-read-one-integer.yaml"
    )
    problem_document = yaml.safe_load(problem_path.read_text(encoding="utf-8"))
    hidden_input = hidden_output.with_suffix(".in").read_bytes()
    problem_document["test_set"]["cases"][0]["checksum"] = hashlib.sha256(
        hidden_input + b"\0" + hidden_output.read_bytes()
    ).hexdigest()
    problem_path.write_text(
        yaml.safe_dump(problem_document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    changed = await run_content_bootstrap(
        manifest,
        problem_slug="js-acm-read-one-integer",
        db=db_session,
        store=fake_object_store,
    )
    assert changed.test_sets.created == 1
    problem = await db_session.scalar(
        select(Problem).where(Problem.slug == "js-acm-read-one-integer")
    )
    assert problem is not None
    versions = (
        await db_session.scalars(
            select(ProblemTestSet)
            .where(ProblemTestSet.problem_id == problem.id)
            .order_by(ProblemTestSet.version)
        )
    ).all()
    assert [item.version for item in versions] == [1, 2]
    assert [item.status for item in versions] == [
        ProblemTestSetStatus.INACTIVE,
        ProblemTestSetStatus.ACTIVE,
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_single_problem_statement_update_does_not_create_test_set(
    db_session: AsyncSession,
    fake_object_store: FakeSourceObjectStore,
    tmp_path: Path,
) -> None:
    await seed_languages(db_session)
    manifest = copy_content(tmp_path)
    await run_content_bootstrap(manifest, db=db_session, store=fake_object_store)
    problem_path = (
        manifest.parent / "problems" / "js-acm" / "js-acm-read-one-integer.yaml"
    )
    problem_document = yaml.safe_load(problem_path.read_text(encoding="utf-8"))
    problem_document["title"] = "边界求和（更新）"
    problem_path.write_text(
        yaml.safe_dump(problem_document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    updated = await run_content_bootstrap(
        manifest,
        problem_slug="js-acm-read-one-integer",
        db=db_session,
        store=fake_object_store,
    )
    assert updated.problems.updated == 1
    assert updated.test_sets.skipped == 1
    assert await db_session.scalar(select(func.count(ProblemTestSet.id))) == 168

    problem_document["test_set"]["version"] = 99
    problem_path.write_text(
        yaml.safe_dump(problem_document, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    version_only = await run_content_bootstrap(
        manifest,
        problem_slug="js-acm-read-one-integer",
        db=db_session,
        store=fake_object_store,
    )
    assert version_only.test_sets.skipped == 1
    assert await db_session.scalar(select(func.count(ProblemTestSet.id))) == 168


class FailingStore(FakeSourceObjectStore):
    async def put_test_data(self, object_key: str, content: bytes) -> None:
        if len(self.test_objects) >= 1:
            raise OSError("secret storage detail")
        await super().put_test_data(object_key, content)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_minio_failure_rolls_back_database_and_cleans_new_objects(
    db_session: AsyncSession,
) -> None:
    await seed_languages(db_session)
    store = FailingStore()
    with pytest.raises(ContentBootstrapError) as failed:
        await run_content_bootstrap(
            CONTENT_ROOT / "manifest.yaml", db=db_session, store=store
        )
    assert failed.value.code == "TEST_DATA_STORAGE_FAILED"
    assert await db_session.scalar(select(func.count(Problem.id))) == 0
    assert store.test_objects == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_database_commit_failure_cleans_orphan_objects(
    db_session: AsyncSession,
    fake_object_store: FakeSourceObjectStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_languages(db_session)
    original_commit = db_session.commit

    async def fail_commit() -> None:
        raise OSError("private database detail")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    bundle = load_content_bundle(
        CONTENT_ROOT / "manifest.yaml", problem_slug="js-acm-read-one-integer"
    )
    with pytest.raises(ContentBootstrapError) as failed:
        await import_content_bundle(db_session, fake_object_store, bundle)
    assert failed.value.code == "CONTENT_IMPORT_FAILED"
    assert fake_object_store.test_objects == {}
    monkeypatch.setattr(db_session, "commit", original_commit)
    await db_session.rollback()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_single_collection_filter_has_no_duplicate_relations(
    db_session: AsyncSession, fake_object_store: FakeSourceObjectStore
) -> None:
    await seed_languages(db_session)
    report = await run_content_bootstrap(
        CONTENT_ROOT / "manifest.yaml",
        collection_slug="js-acm-single-value",
        db=db_session,
        store=fake_object_store,
    )
    assert report.collections.created == 1
    assert await db_session.scalar(select(func.count(CollectionProblem.problem_id))) == 8
    second = await run_content_bootstrap(
        CONTENT_ROOT / "manifest.yaml",
        collection_slug="js-acm-single-value",
        db=db_session,
        store=fake_object_store,
    )
    assert second.collections.skipped == 1
    assert await db_session.scalar(select(func.count(CollectionProblem.problem_id))) == 8


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reports_and_public_api_never_contain_hidden_material(
    client,
    db_session: AsyncSession,
    fake_object_store: FakeSourceObjectStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await seed_languages(db_session)
    report = await run_content_bootstrap(
        CONTENT_ROOT / "manifest.yaml", db=db_session, store=fake_object_store
    )
    serialized_report = report.model_dump_json()
    public_problems = await client.get("/api/v1/problems?page_size=100")
    public_collections = await client.get("/api/v1/collections?page_size=100")
    public_daily = await client.get("/api/v1/daily-challenge")
    captured = capsys.readouterr()
    combined = (
        serialized_report
        + public_problems.text
        + public_collections.text
        + public_daily.text
        + captured.out
        + captured.err
    )
    assert public_problems.status_code == 200
    assert public_collections.status_code == 200
    assert public_daily.status_code == 200
    for forbidden in (
        "test-data",
        "input_object_key",
        "output_object_key",
        "checksum",
        "6202anerAedoC",
        "-1000000000 1000000000",
    ):
        assert forbidden not in combined
