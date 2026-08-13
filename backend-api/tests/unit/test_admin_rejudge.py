from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.problem import Language, Problem, ProblemDifficulty, ProblemVisibility
from app.models.submission import (
    Outbox,
    RejudgeTask,
    Submission,
    SubmissionAttempt,
    SubmissionMode,
    SubmissionStatus,
)
from app.models.user import User
from tests.unit.conftest import active_test_set


async def register(client: AsyncClient, username: str) -> tuple[dict[str, str], str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "safe-password-123",
            "nickname": username,
        },
    )
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["id"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejudge_requires_admin_and_creates_new_snapshot(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    normal_headers, normal_id = await register(client, "rejudge_normal")
    admin_headers, admin_id = await register(client, "rejudge_admin")
    admin = await db_session.get(User, UUID(admin_id))
    assert admin is not None
    admin.is_admin = True
    problem = Problem(
        slug="rejudge-problem",
        title="重判题",
        description="d",
        difficulty=ProblemDifficulty.EASY,
        input_description="i",
        output_description="o",
        visibility=ProblemVisibility.PUBLIC,
    )
    test_set = active_test_set(problem)
    language = Language(
        slug="python",
        display_name="Python",
        version="3.12",
        monaco_language="python",
        source_filename="main.py",
        run_command="private",
        docker_image="private",
        enabled=True,
    )
    db_session.add_all([problem, test_set, language])
    await db_session.flush()
    original = Submission(
        id=uuid4(),
        user_id=UUID(normal_id),
        problem_id=problem.id,
        language_id=language.id,
        status=SubmissionStatus.WRONG_ANSWER,
        mode=SubmissionMode.JUDGE,
        test_set_id=test_set.id,
        problem_version=problem.version,
        time_limit_ms_snapshot=1000,
        memory_limit_mb_snapshot=256,
        source_object_key="internal/source",
        source_checksum="0" * 64,
    )
    db_session.add(original)
    await db_session.commit()

    path = "/api/v1/admin/rejudge/submissions"
    payload = {"submission_id": str(original.id)}
    assert (await client.post(path, json=payload)).status_code == 401
    assert (await client.post(path, json=payload, headers=normal_headers)).status_code == 403
    response = await client.post(path, json=payload, headers=admin_headers)
    assert response.status_code == 202
    assert response.json()["total_count"] == 1
    assert response.json()["status"] == "queued"
    submissions = (await db_session.scalars(select(Submission))).all()
    assert len(submissions) == 1
    attempt = await db_session.scalar(
        select(SubmissionAttempt).where(SubmissionAttempt.kind == "rejudge")
    )
    assert attempt is not None
    assert attempt.submission_id == original.id
    assert attempt.test_set_id == test_set.id
    assert attempt.status is SubmissionStatus.PENDING
    assert await db_session.scalar(select(func.count(RejudgeTask.id))) == 1
    assert await db_session.scalar(select(func.count(Outbox.id))) == 1
    assert "source_object_key" not in response.text
    assert "attempt_id" not in response.text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_rejudge_rejects_pending_submission(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, admin_id = await register(client, "rejudge_pending_admin")
    admin = await db_session.get(User, UUID(admin_id))
    assert admin is not None
    admin.is_admin = True
    problem = Problem(
        slug="pending-rejudge",
        title="pending",
        description="d",
        difficulty=ProblemDifficulty.EASY,
        input_description="i",
        output_description="o",
        visibility=ProblemVisibility.PUBLIC,
    )
    test_set = active_test_set(problem)
    language = Language(
        slug="cpp",
        display_name="C++",
        version="20",
        monaco_language="cpp",
        source_filename="main.cpp",
        run_command="private",
        docker_image="private",
        enabled=True,
    )
    db_session.add_all([problem, test_set, language])
    await db_session.flush()
    submission = Submission(
        user_id=admin.id,
        problem_id=problem.id,
        language_id=language.id,
        status=SubmissionStatus.PENDING,
        mode=SubmissionMode.JUDGE,
        test_set_id=test_set.id,
        source_object_key="source",
        source_checksum="0" * 64,
    )
    db_session.add(submission)
    await db_session.commit()
    response = await client.post(
        "/api/v1/admin/rejudge/submissions",
        json={"submission_id": str(submission.id)},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SUBMISSION_NOT_REJUDGEABLE"
