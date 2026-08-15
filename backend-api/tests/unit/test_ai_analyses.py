from datetime import datetime, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ai import AIAnalysis, AIAnalysisStatus, AuditLog
from app.models.problem import Language, Problem, ProblemDifficulty, ProblemVisibility
from app.models.submission import Outbox, Submission, SubmissionStatus
from tests.unit.conftest import active_test_set

DIAGNOSTIC_REPORT = {
    "runtime_mismatch": {"detected": False, "summary": "运行模式一致"},
    "input_reading_issue": {"detected": True, "summary": "可能未正确读取 stdin"},
    "line_parsing_issue": {"detected": False, "summary": "未发现按行解析问题"},
    "token_parsing_issue": {"detected": False, "summary": "未发现 token 解析问题"},
    "whitespace_issue": {"detected": False, "summary": "未发现空白问题"},
    "eof_issue": {"detected": False, "summary": "未发现 EOF 问题"},
    "numeric_issue": {"detected": False, "summary": "未发现数值问题"},
    "output_format_issue": {"detected": True, "summary": "stdout 格式可能不一致"},
    "performance_issue": {"detected": False, "summary": "未发现性能问题"},
}


@pytest.fixture(autouse=True)
def enable_ai_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_analysis_enabled", True)


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


async def seed_catalog(db: AsyncSession) -> tuple[Problem, Language]:
    problem = Problem(
        slug="ai-review-problem",
        title="AI review",
        description="public statement",
        difficulty=ProblemDifficulty.MEDIUM,
        input_description="stdin",
        output_description="stdout",
        visibility=ProblemVisibility.PUBLIC,
    )
    language = Language(
        slug="nodejs",
        display_name="Node.js",
        version="22",
        monaco_language="javascript",
        source_filename="main.js",
        run_command="internal",
        docker_image="internal",
        enabled=True,
    )
    db.add_all([problem, language, active_test_set(problem)])
    await db.commit()
    return problem, language


async def create_failed_submission(
    client: AsyncClient,
    db: AsyncSession,
    headers: dict[str, str],
    problem: Problem,
    status: SubmissionStatus = SubmissionStatus.WRONG_ANSWER,
) -> Submission:
    response = await client.post(
        "/api/v1/submissions",
        headers=headers,
        json={
            "problem_id": problem.id,
            "language": "nodejs",
            "source_code": "console.log('user source')",
            "mode": "judge",
        },
    )
    assert response.status_code == 202
    submission = await db.get(Submission, UUID(response.json()["id"]))
    assert submission is not None
    submission.status = status
    submission.compiler_output = "compile output without hidden cases"
    submission.error_message = "aggregate diagnostic"
    submission.judged_at = datetime.now(timezone.utc)
    await db.commit()
    return submission


@pytest.mark.unit
@pytest.mark.asyncio
async def test_owner_can_queue_failed_analysis_without_sensitive_payload(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, _ = await seed_catalog(db_session)
    headers = await register(client, "ai_owner")
    submission = await create_failed_submission(client, db_session, headers, problem)

    response = await client.post(
        f"/api/v1/submissions/{submission.id}/ai-analysis", headers=headers
    )

    assert response.status_code == 202
    body = response.json()
    assert body["analysis"]["status"] == "pending"
    event = (
        await db_session.scalars(
            select(Outbox).where(Outbox.event_type == "ai.analysis.requested")
        )
    ).one()
    assert set(event.payload) == {"analysis_id"}
    serialized = str(body) + str(event.payload)
    for forbidden in ("source_object_key", "user source", "compile output", "hidden"):
        assert forbidden not in serialized
    assert await db_session.scalar(select(func.count(AuditLog.id))) >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_foreign_and_non_failed_submissions_cannot_be_analyzed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, _ = await seed_catalog(db_session)
    owner = await register(client, "ai_submission_owner")
    stranger = await register(client, "ai_submission_stranger")
    failed = await create_failed_submission(client, db_session, owner, problem)

    foreign = await client.post(
        f"/api/v1/submissions/{failed.id}/ai-analysis", headers=stranger
    )
    assert foreign.status_code == 404

    failed.status = SubmissionStatus.ACCEPTED
    await db_session.commit()
    accepted = await client.post(
        f"/api/v1/submissions/{failed.id}/ai-analysis", headers=owner
    )
    assert accepted.status_code == 409
    assert accepted.json()["detail"]["code"] == "SUBMISSION_NOT_ANALYZABLE"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ai_quota_returns_standard_429(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    problem, _ = await seed_catalog(db_session)
    headers = await register(client, "ai_quota_user")
    monkeypatch.setattr(settings, "ai_analysis_daily_quota", 1)
    first = await create_failed_submission(client, db_session, headers, problem)
    await client.post(f"/api/v1/submissions/{first.id}/ai-analysis", headers=headers)

    second = Submission(
        user_id=first.user_id,
        problem_id=first.problem_id,
        language_id=first.language_id,
        status=SubmissionStatus.RUNTIME_ERROR,
        test_set_id=first.test_set_id,
        problem_version=first.problem_version,
        time_limit_ms_snapshot=first.time_limit_ms_snapshot,
        memory_limit_mb_snapshot=first.memory_limit_mb_snapshot,
        source_object_key="submissions/another/source.py",
        source_checksum="1" * 64,
        judged_at=datetime.now(timezone.utc),
    )
    db_session.add(second)
    await db_session.commit()
    limited = await client.post(
        f"/api/v1/submissions/{second.id}/ai-analysis", headers=headers
    )

    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "AI_QUOTA_EXCEEDED"
    assert int(limited.headers["retry-after"]) > 0
    assert await db_session.scalar(select(func.count(AIAnalysis.id))) == 1
    quota_audit = await db_session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "ai.analysis.quota_rejected"
        )
    )
    assert quota_audit == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_completed_fingerprint_cache_does_not_consume_model_quota(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, language = await seed_catalog(db_session)
    headers = await register(client, "ai_cache_user")
    first = await create_failed_submission(client, db_session, headers, problem)
    first_response = await client.post(
        f"/api/v1/submissions/{first.id}/ai-analysis", headers=headers
    )
    first_analysis = await db_session.get(
        AIAnalysis, UUID(first_response.json()["analysis"]["id"])
    )
    assert first_analysis is not None
    first_analysis.status = AIAnalysisStatus.COMPLETED
    first_analysis.diagnostic_report = DIAGNOSTIC_REPORT
    first_analysis.failure_reason = "legacy algorithm analysis"
    first_analysis.time_complexity = "O(n^2)"
    first_analysis.space_complexity = "O(n)"
    first_analysis.suggestions = ["cached suggestion"]
    first_analysis.guiding_questions = ["cached question"]
    first_analysis.confidence = "medium"
    first_analysis.completed_at = datetime.now(timezone.utc)

    second = Submission(
        user_id=first.user_id,
        problem_id=problem.id,
        language_id=language.id,
        status=SubmissionStatus.WRONG_ANSWER,
        test_set_id=first.test_set_id,
        problem_version=first.problem_version,
        time_limit_ms_snapshot=first.time_limit_ms_snapshot,
        memory_limit_mb_snapshot=first.memory_limit_mb_snapshot,
        source_object_key="submissions/cache/source.py",
        source_checksum=first.source_checksum,
        compiler_output=first.compiler_output,
        error_message=first.error_message,
        time_used_ms=first.time_used_ms,
        memory_used_kb=first.memory_used_kb,
        passed_case_count=first.passed_case_count,
        total_case_count=first.total_case_count,
        judged_at=datetime.now(timezone.utc),
    )
    db_session.add(second)
    await db_session.commit()

    cached = await client.post(
        f"/api/v1/submissions/{second.id}/ai-analysis", headers=headers
    )

    assert cached.status_code == 202
    assert cached.json()["reused"] is True
    assert cached.json()["quota"] is None
    assert cached.json()["analysis"]["input_reading_issue"]["detected"] is True
    assert cached.json()["analysis"]["output_format_issue"]["detected"] is True
    assert cached.json()["analysis"]["cached"] is True
    cached_analysis = await db_session.scalar(
        select(AIAnalysis).where(AIAnalysis.submission_id == second.id)
    )
    assert cached_analysis is not None
    assert cached_analysis.failure_reason is None
    assert cached_analysis.time_complexity is None
    assert cached_analysis.space_complexity is None
    ai_events = await db_session.scalar(
        select(func.count(Outbox.id)).where(Outbox.event_type == "ai.analysis.requested")
    )
    assert ai_events == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_public_diagnostic_dto_filters_untrusted_sensitive_text(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, _ = await seed_catalog(db_session)
    headers = await register(client, "ai_public_filter_user")
    submission = await create_failed_submission(client, db_session, headers, problem)
    queued = await client.post(
        f"/api/v1/submissions/{submission.id}/ai-analysis", headers=headers
    )
    analysis = await db_session.get(AIAnalysis, UUID(queued.json()["analysis"]["id"]))
    assert analysis is not None
    analysis.status = AIAnalysisStatus.COMPLETED
    analysis.diagnostic_report = {
        **DIAGNOSTIC_REPORT,
        "input_reading_issue": {
            "detected": True,
            "summary": "hidden_input=s3://private-bucket/case-1.in",
            "object_key": "private-bucket/case-1.in",
        },
        "reference_solution": "must not be serialized",
    }
    analysis.suggestions = ["read MinIO://private-bucket/case-1.out"]
    analysis.guiding_questions = ["Can you inspect the public input format?"]
    analysis.confidence = "high"
    analysis.completed_at = datetime.now(timezone.utc)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/submissions/{submission.id}/ai-analysis", headers=headers
    )

    assert response.status_code == 200
    serialized = response.text
    for forbidden in (
        "private-bucket",
        "object_key",
        "reference_solution",
        "hidden_input",
        "s3://",
        "MinIO://",
    ):
        assert forbidden not in serialized
    assert response.json()["input_reading_issue"]["summary"] == "诊断内容已因安全策略隐藏。"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_non_javascript_runtime_is_not_analyzable(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, language = await seed_catalog(db_session)
    headers = await register(client, "ai_runtime_guard_user")
    submission = await create_failed_submission(client, db_session, headers, problem)
    language.slug = "python"
    await db_session.commit()

    response = await client.post(
        f"/api/v1/submissions/{submission.id}/ai-analysis", headers=headers
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "RUNTIME_NOT_SUPPORTED"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_output_limit_exceeded_can_request_io_diagnosis(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, _ = await seed_catalog(db_session)
    headers = await register(client, "ai_output_limit_user")
    submission = await create_failed_submission(
        client,
        db_session,
        headers,
        problem,
        status=SubmissionStatus.OUTPUT_LIMIT_EXCEEDED,
    )

    response = await client.post(
        f"/api/v1/submissions/{submission.id}/ai-analysis", headers=headers
    )

    assert response.status_code == 202
    assert response.json()["analysis"]["status"] == "pending"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unconfigured_provider_degrades_immediately_without_queue_or_polling_state(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem, _ = await seed_catalog(db_session)
    headers = await register(client, "ai_unconfigured_user")
    submission = await create_failed_submission(client, db_session, headers, problem)
    monkeypatch.setattr(settings, "ai_analysis_enabled", False)

    response = await client.post(
        f"/api/v1/submissions/{submission.id}/ai-analysis", headers=headers
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "AI_PROVIDER_NOT_CONFIGURED",
        "message": "AI input/output diagnosis is not configured",
    }
    assert await db_session.scalar(select(func.count(AIAnalysis.id))) == 0
    ai_events = await db_session.scalar(
        select(func.count(Outbox.id)).where(Outbox.event_type == "ai.analysis.requested")
    )
    assert ai_events == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_ai_control_plane_counters(
    client: AsyncClient,
) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "codearena_ai_analysis_requests_total" in response.text
    assert "codearena_ai_analysis_quota_rejections_total" in response.text
