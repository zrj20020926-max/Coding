import hashlib
import json
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.main import app
from app.models.problem import Language, Problem, ProblemDifficulty, ProblemVisibility
from app.models.submission import Outbox, Submission, SubmissionMode, SubmissionStatus
from app.services.outbox import publish_outbox_batch
from app.services.submissions import InvalidSubmissionTransition, transition_submission_status
from tests.unit.conftest import FakeSourceObjectStore, active_test_set


async def register(client: AsyncClient, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "safe-password-123",
            "nickname": username,
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def seed_submission_catalog(db: AsyncSession) -> tuple[Problem, Problem]:
    public = Problem(
        slug="control-plane-problem",
        title="Control Plane",
        description="description",
        difficulty=ProblemDifficulty.EASY,
        input_description="stdin",
        output_description="stdout",
        visibility=ProblemVisibility.PUBLIC,
    )
    draft = Problem(
        slug="control-plane-draft",
        title="Draft",
        description="hidden",
        difficulty=ProblemDifficulty.EASY,
        input_description="stdin",
        output_description="stdout",
        visibility=ProblemVisibility.DRAFT,
    )
    db.add_all(
        [
            public,
            draft,
            active_test_set(public),
            Language(
                slug="python",
                display_name="Python",
                version="3.12",
                monaco_language="python",
                source_filename="main.py",
                run_command="private runtime",
                docker_image="private image",
                enabled=True,
            ),
            Language(
                slug="disabled",
                display_name="Disabled",
                version="1",
                monaco_language="text",
                source_filename="main.txt",
                compile_command="private compiler",
                run_command="private runtime",
                docker_image="private image",
                enabled=False,
            ),
        ]
    )
    await db.commit()
    return public, draft


def request(
    problem_id: int,
    source: str = "print(input())",
    mode: str = "judge",
) -> dict[str, Any]:
    return {
        "problem_id": problem_id,
        "language": "python",
        "source_code": source,
        "mode": mode,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_submission_is_stored_with_pending_outbox_and_safe_response(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_object_store: FakeSourceObjectStore,
) -> None:
    problem, _ = await seed_submission_catalog(db_session)
    headers = await register(client, "submit_owner")
    headers["Idempotency-Key"] = "editor-click-1"

    response = await client.post("/api/v1/submissions", json=request(problem.id), headers=headers)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "Pending"
    assert body["mode"] == "judge"
    assert body["idempotent_replay"] is False
    submission = (await db_session.scalars(select(Submission))).one()
    event = (await db_session.scalars(select(Outbox))).one()
    assert submission.source_code is None
    assert submission.source_checksum == hashlib.sha256(b"print(input())").hexdigest()
    assert fake_object_store.objects[submission.source_object_key] == b"print(input())"
    assert event.aggregate_id == submission.id
    assert event.published_at is None
    assert set(event.payload) == {"event_id", "submission_id"}
    assert submission.test_set_id is not None
    assert submission.problem_version == problem.version
    assert submission.time_limit_ms_snapshot == problem.time_limit_ms
    assert submission.memory_limit_mb_snapshot == problem.memory_limit_mb
    serialized = json.dumps(body)
    for forbidden in (
        "source_object_key",
        "object_key",
        "queue_message_id",
        "compile_command",
        "docker_image",
        "compiler_output",
    ):
        assert forbidden not in serialized


@pytest.mark.unit
@pytest.mark.asyncio
async def test_idempotency_replay_creates_one_submission_and_rejects_key_reuse(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, _ = await seed_submission_catalog(db_session)
    headers = await register(client, "idempotent_owner")
    headers["Idempotency-Key"] = "same-editor-click"

    first = await client.post("/api/v1/submissions", json=request(problem.id), headers=headers)
    replay = await client.post("/api/v1/submissions", json=request(problem.id), headers=headers)
    conflict = await client.post(
        "/api/v1/submissions", json=request(problem.id, "print(42)"), headers=headers
    )

    assert first.status_code == replay.status_code == 202
    assert first.json()["id"] == replay.json()["id"]
    assert replay.json()["idempotent_replay"] is True
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert await db_session.scalar(select(func.count(Submission.id))) == 1
    assert await db_session.scalar(select(func.count(Outbox.id))) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sample_and_formal_runs_are_distinct_and_detail_is_owner_safe(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    problem, _ = await seed_submission_catalog(db_session)
    headers = await register(client, "sample_owner")
    sample_headers = {**headers, "Idempotency-Key": "run-sample-1"}
    judge_headers = {**headers, "Idempotency-Key": "submit-judge-1"}

    sample = await client.post(
        "/api/v1/submissions",
        json=request(problem.id, mode="sample"),
        headers=sample_headers,
    )
    formal = await client.post(
        "/api/v1/submissions",
        json=request(problem.id, mode="judge"),
        headers=judge_headers,
    )
    detail = await client.get(
        f"/api/v1/submissions/{sample.json()['id']}", headers=headers
    )

    assert sample.status_code == formal.status_code == 202
    assert sample.json()["id"] != formal.json()["id"]
    assert sample.json()["mode"] == "sample"
    assert formal.json()["mode"] == "judge"
    assert detail.status_code == 200
    assert detail.json()["source_code"] == "print(input())"
    assert detail.json()["sample_output"] is None
    assert "source_object_key" not in detail.text
    modes = set((await db_session.scalars(select(Submission.mode))).all())
    assert modes == {SubmissionMode.SAMPLE, SubmissionMode.JUDGE}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_storage_failure_does_not_create_database_records(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_object_store: FakeSourceObjectStore,
) -> None:
    problem, _ = await seed_submission_catalog(db_session)
    headers = await register(client, "storage_failure")
    fake_object_store.fail_put = True

    response = await client.post("/api/v1/submissions", json=request(problem.id), headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "SOURCE_STORAGE_UNAVAILABLE"
    assert await db_session.scalar(select(func.count(Submission.id))) == 0
    assert await db_session.scalar(select(func.count(Outbox.id))) == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rate_limit_and_catalog_validation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, draft = await seed_submission_catalog(db_session)
    headers = await register(client, "rate_limited")

    first = await client.post("/api/v1/submissions", json=request(problem.id), headers=headers)
    limited = await client.post(
        "/api/v1/submissions", json=request(problem.id, "print(2)"), headers=headers
    )
    draft_response = await client.post(
        "/api/v1/submissions", json=request(draft.id), headers=headers
    )
    disabled = await client.post(
        "/api/v1/submissions",
        json={**request(problem.id), "language": "disabled"},
        headers=headers,
    )
    oversized = await client.post(
        "/api/v1/submissions",
        json=request(problem.id, "x" * (settings.submission_source_max_bytes + 1)),
        headers=headers,
    )

    assert first.status_code == 202
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == str(settings.submission_min_interval_seconds)
    assert draft_response.status_code == 404
    assert disabled.status_code == 400
    assert oversized.status_code == 413


@pytest.mark.unit
@pytest.mark.asyncio
async def test_foreign_submission_is_hidden_and_problem_filter_works(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, _ = await seed_submission_catalog(db_session)
    owner_headers = await register(client, "submission_owner")
    stranger_headers = await register(client, "submission_stranger")
    created = await client.post(
        "/api/v1/submissions", json=request(problem.id), headers=owner_headers
    )
    submission_id = created.json()["id"]

    assert (
        await client.get(f"/api/v1/submissions/{submission_id}", headers=stranger_headers)
    ).status_code == 404
    stranger_list = await client.get("/api/v1/submissions", headers=stranger_headers)
    owner_list = await client.get(
        f"/api/v1/submissions?problem_id={problem.id}", headers=owner_headers
    )
    empty_filter = await client.get(
        f"/api/v1/submissions?problem_id={problem.id + 999}", headers=owner_headers
    )
    assert stranger_list.json()["total"] == 0
    assert owner_list.json()["total"] == 1
    assert empty_filter.json()["total"] == 0


class StubPublisherRedis:
    def __init__(self, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.published: dict[str, str] = {}
        self.stream_entries: list[str] = []

    async def eval(self, _script: str, _numkeys: int, *args: str) -> str:
        if self.unavailable:
            raise ConnectionError("Redis unavailable")
        dedup_key = args[0]
        event_id = args[3]
        if dedup_key not in self.published:
            message_id = f"1000-{len(self.stream_entries)}"
            self.published[dedup_key] = message_id
            self.stream_entries.append(event_id)
        return self.published[dedup_key]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_outage_leaves_outbox_retryable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, _ = await seed_submission_catalog(db_session)
    headers = await register(client, "redis_outage")
    created = await client.post("/api/v1/submissions", json=request(problem.id), headers=headers)
    assert created.status_code == 202

    assert await publish_outbox_batch(db_session, StubPublisherRedis(unavailable=True)) == 0
    event = (await db_session.scalars(select(Outbox))).one()
    assert event.published_at is None
    assert event.attempts == 1
    assert "Redis unavailable" in event.last_error
    assert (await db_session.scalars(select(Submission))).one().status == SubmissionStatus.PENDING


@pytest.mark.unit
@pytest.mark.asyncio
async def test_duplicate_outbox_delivery_is_deduplicated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, _ = await seed_submission_catalog(db_session)
    headers = await register(client, "duplicate_delivery")
    await client.post("/api/v1/submissions", json=request(problem.id), headers=headers)
    cache = StubPublisherRedis()

    assert await publish_outbox_batch(db_session, cache) == 1
    event = (await db_session.scalars(select(Outbox))).one()
    first_message_id = event.stream_message_id
    event.published_at = None
    event.next_attempt_at = event.created_at
    await db_session.commit()
    assert await publish_outbox_batch(db_session, cache) == 1

    assert len(cache.stream_entries) == 1
    assert event.stream_message_id == first_message_id


@pytest.mark.unit
def test_submission_state_machine_rejects_skips_and_terminal_reentry() -> None:
    submission = Submission(
        user_id="00000000-0000-0000-0000-000000000001",
        problem_id=1,
        language_id=1,
        source_object_key="internal",
        source_checksum="0" * 64,
        status=SubmissionStatus.PENDING,
    )
    with pytest.raises(InvalidSubmissionTransition):
        transition_submission_status(submission, SubmissionStatus.ACCEPTED)
    transition_submission_status(submission, SubmissionStatus.COMPILING)
    transition_submission_status(submission, SubmissionStatus.RUNNING)
    transition_submission_status(submission, SubmissionStatus.ACCEPTED)
    assert submission.judged_at is not None
    with pytest.raises(InvalidSubmissionTransition):
        transition_submission_status(submission, SubmissionStatus.RUNNING)


@pytest.mark.unit
def test_submission_openapi_does_not_expose_internal_runtime_fields() -> None:
    openapi = json.dumps(app.openapi())
    for forbidden in (
        "source_object_key",
        "queue_message_id",
        "compile_command",
        "docker_image",
    ):
        assert forbidden not in openapi
    assert "compiler_output" in openapi
    assert "source_code" in openapi
