# ruff: noqa: UP045
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from time import time
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.metrics import (
    AI_ANALYSIS_CACHE_HITS,
    AI_ANALYSIS_QUOTA_REJECTIONS,
    AI_ANALYSIS_REQUESTS,
)
from app.models.ai import AIAnalysis, AIAnalysisStatus, AIUsageRecord, AuditLog
from app.models.problem import ProblemVisibility
from app.models.submission import Outbox, Submission, SubmissionStatus
from app.schemas.ai import AIAnalysisPublic, AIAnalysisTriggered, AIQuotaPublic

ANALYZABLE_FAILURES = {
    SubmissionStatus.WRONG_ANSWER,
    SubmissionStatus.COMPILE_ERROR,
    SubmissionStatus.RUNTIME_ERROR,
    SubmissionStatus.TIME_LIMIT_EXCEEDED,
    SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
}


def ai_error(
    http_status: int,
    code: str,
    message: str,
    retry_after: Optional[int] = None,
) -> HTTPException:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return HTTPException(
        status_code=http_status,
        detail={"code": code, "message": message},
        headers=headers,
    )


def _fingerprint(submission: Submission) -> str:
    safe_summary = {
        "problem_id": submission.problem_id,
        "problem_updated_at": submission.problem.updated_at.isoformat(),
        "language": submission.language.slug,
        "source_checksum": submission.source_checksum,
        "status": submission.status.value,
        "compiler_output": (submission.compiler_output or "")[:16_000],
        "time_used_ms": submission.time_used_ms,
        "memory_used_kb": submission.memory_used_kb,
        "passed_case_count": submission.passed_case_count,
        "total_case_count": submission.total_case_count,
    }
    encoded = json.dumps(safe_summary, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


async def _consume_quota(cache: Redis, user_id: UUID) -> AIQuotaPublic:
    window = settings.ai_analysis_quota_window_seconds
    bucket = int(time()) // window
    key = f"ai:quota:{user_id}:{bucket}"
    try:
        async with cache.pipeline(transaction=True) as pipeline:
            pipeline.incr(key)
            pipeline.expire(key, window * 2)
            results = await pipeline.execute()
    except Exception as exc:
        AI_ANALYSIS_QUOTA_REJECTIONS.labels("unavailable").inc()
        raise ai_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AI_QUOTA_UNAVAILABLE",
            "AI analysis is temporarily unavailable",
        ) from exc
    count = int(results[0])
    retry_after = max(1, window - (int(time()) % window))
    if count > settings.ai_analysis_daily_quota:
        AI_ANALYSIS_QUOTA_REJECTIONS.labels("exceeded").inc()
        raise ai_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "AI_QUOTA_EXCEEDED",
            "AI analysis quota has been used up; retry after the quota resets",
            retry_after,
        )
    return AIQuotaPublic(
        limit=settings.ai_analysis_daily_quota,
        remaining=max(0, settings.ai_analysis_daily_quota - count),
        reset_after_seconds=retry_after,
    )


def to_ai_public(analysis: AIAnalysis) -> AIAnalysisPublic:
    return AIAnalysisPublic(
        id=analysis.id,
        submission_id=analysis.submission_id,
        status=analysis.status,
        failure_reason=analysis.failure_reason,
        time_complexity=analysis.time_complexity,
        space_complexity=analysis.space_complexity,
        suggestions=analysis.suggestions or [],
        guiding_questions=analysis.guiding_questions or [],
        confidence=analysis.confidence,
        cached=analysis.cached_from_id is not None,
        retry_count=analysis.retry_count,
        error_code=analysis.error_code,
        error_message=analysis.error_message,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
        completed_at=analysis.completed_at,
    )


async def _owned_submission(
    db: AsyncSession, submission_id: UUID, user_id: UUID
) -> Optional[Submission]:
    return await db.scalar(
        select(Submission)
        .options(joinedload(Submission.problem), joinedload(Submission.language))
        .where(Submission.id == submission_id, Submission.user_id == user_id)
        .with_for_update(of=Submission)
    )


async def get_owned_analysis(
    db: AsyncSession, submission_id: UUID, user_id: UUID
) -> Optional[AIAnalysis]:
    return await db.scalar(
        select(AIAnalysis).where(
            AIAnalysis.submission_id == submission_id,
            AIAnalysis.user_id == user_id,
        )
    )


async def trigger_analysis(
    db: AsyncSession,
    cache: Redis,
    submission_id: UUID,
    user_id: UUID,
    request_id: str | None,
) -> AIAnalysisTriggered:
    submission = await _owned_submission(db, submission_id, user_id)
    if submission is None:
        raise ai_error(status.HTTP_404_NOT_FOUND, "SUBMISSION_NOT_FOUND", "submission not found")
    if submission.problem.visibility is not ProblemVisibility.PUBLIC:
        raise ai_error(status.HTTP_404_NOT_FOUND, "SUBMISSION_NOT_FOUND", "submission not found")
    if submission.status not in ANALYZABLE_FAILURES:
        raise ai_error(
            status.HTTP_409_CONFLICT,
            "SUBMISSION_NOT_ANALYZABLE",
            "only completed failed submissions can be analyzed",
        )

    existing = await get_owned_analysis(db, submission_id, user_id)
    if existing is not None and existing.status is not AIAnalysisStatus.FAILED:
        AI_ANALYSIS_REQUESTS.labels("existing").inc()
        db.add(
            AuditLog(
                actor_user_id=user_id,
                action="ai.analysis.existing_returned",
                target_type="ai_analysis",
                target_id=str(existing.id),
                request_id=request_id,
                metadata_json={"submission_id": str(submission.id)},
            )
        )
        await db.commit()
        return AIAnalysisTriggered(
            analysis=to_ai_public(existing),
            quota=None,
            reused=True,
        )

    fingerprint = _fingerprint(submission)
    cached = await db.scalar(
        select(AIAnalysis)
        .where(
            AIAnalysis.request_fingerprint == fingerprint,
            AIAnalysis.status == AIAnalysisStatus.COMPLETED,
            AIAnalysis.user_id == user_id,
            AIAnalysis.submission_id != submission_id,
        )
        .order_by(AIAnalysis.completed_at.desc())
        .limit(1)
    )
    now = datetime.now(timezone.utc)
    failure_summary = json.dumps(
        {
            "status": submission.status.value,
            "time_used_ms": submission.time_used_ms,
            "memory_used_kb": submission.memory_used_kb,
            "passed_case_count": submission.passed_case_count,
            "total_case_count": submission.total_case_count,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    quota = None
    if cached is None:
        try:
            quota = await _consume_quota(cache, user_id)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            db.add(
                AuditLog(
                    actor_user_id=user_id,
                    action="ai.analysis.quota_rejected",
                    target_type="submission",
                    target_id=str(submission.id),
                    request_id=request_id,
                    metadata_json={"error_code": detail.get("code", "AI_QUOTA_REJECTED")},
                )
            )
            await db.commit()
            raise
    if existing is None:
        analysis = AIAnalysis(
            submission_id=submission.id,
            user_id=user_id,
            request_fingerprint=fingerprint,
            failure_summary=failure_summary,
        )
        db.add(analysis)
        await db.flush()
    else:
        analysis = existing
        analysis.status = AIAnalysisStatus.PENDING
        analysis.request_fingerprint = fingerprint
        analysis.failure_summary = failure_summary
        analysis.failure_reason = None
        analysis.time_complexity = None
        analysis.space_complexity = None
        analysis.suggestions = None
        analysis.guiding_questions = None
        analysis.confidence = None
        analysis.error_code = None
        analysis.error_message = None
        analysis.started_at = None
        analysis.completed_at = None

    reused = cached is not None
    if cached is not None:
        AI_ANALYSIS_CACHE_HITS.inc()
        AI_ANALYSIS_REQUESTS.labels("cache_hit").inc()
        analysis.status = AIAnalysisStatus.COMPLETED
        analysis.failure_reason = cached.failure_reason
        analysis.time_complexity = cached.time_complexity
        analysis.space_complexity = cached.space_complexity
        analysis.suggestions = list(cached.suggestions or [])
        analysis.guiding_questions = list(cached.guiding_questions or [])
        analysis.confidence = cached.confidence
        analysis.cached_from_id = cached.id
        analysis.completed_at = now
        db.add(
            AIUsageRecord(
                analysis_id=analysis.id,
                user_id=user_id,
                provider=cached.provider,
                model_name=cached.model_name,
                cache_hit=True,
            )
        )
    else:
        AI_ANALYSIS_REQUESTS.labels("queued").inc()
        analysis.cached_from_id = None
        db.add(
            Outbox(
                aggregate_type="ai_analysis",
                aggregate_id=analysis.id,
                event_type="ai.analysis.requested",
                payload={"analysis_id": str(analysis.id)},
            )
        )

    db.add(
        AuditLog(
            actor_user_id=user_id,
            action="ai.analysis.reused" if reused else "ai.analysis.requested",
            target_type="ai_analysis",
            target_id=str(analysis.id),
            request_id=request_id,
            metadata_json={"submission_id": str(submission.id), "cache_hit": reused},
        )
    )
    await db.commit()
    await db.refresh(analysis)
    return AIAnalysisTriggered(analysis=to_ai_public(analysis), quota=quota, reused=reused)
