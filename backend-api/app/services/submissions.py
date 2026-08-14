from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from math import ceil
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.models.problem import (
    Language,
    Problem,
    ProblemVisibility,
    TestGroup,
    TestSet,
    TestSetStatus,
)
from app.models.submission import (
    Outbox,
    Submission,
    SubmissionAttempt,
    SubmissionAttemptGroupResult,
    SubmissionMode,
    SubmissionStatus,
)
from app.models.user import User
from app.schemas.submission import (
    SubmissionAttemptGroupPublic,
    SubmissionAttemptPublic,
    SubmissionCreated,
    SubmissionDetail,
    SubmissionLanguagePublic,
    SubmissionPage,
    SubmissionProblemPublic,
    SubmissionPublic,
)
from app.services.object_storage import SourceObjectStore


def submission_error(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


def _fingerprint(
    problem_id: int,
    language_slug: str,
    checksum: str,
    mode: SubmissionMode,
    custom_input_checksum: str | None,
) -> str:
    serialized = json.dumps(
        {
            "problem_id": problem_id,
            "language": language_slug,
            "checksum": checksum,
            "mode": mode.value,
            "custom_input_checksum": custom_input_checksum,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    if not 1 <= len(value) <= 128 or value != value.strip() or not value.isprintable():
        raise submission_error(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_IDEMPOTENCY_KEY",
            "Idempotency-Key must be 1-128 printable characters without surrounding spaces",
        )
    return value


async def _find_idempotent_submission(
    db: AsyncSession, user_id: UUID, idempotency_key: str | None
) -> Submission | None:
    if idempotency_key is None:
        return None
    return await db.scalar(
        select(Submission)
        .options(joinedload(Submission.problem), joinedload(Submission.language))
        .where(
            Submission.user_id == user_id,
            Submission.idempotency_key == idempotency_key,
        )
    )


async def _enforce_submission_rate(
    cache: Redis, user_id: UUID, mode: SubmissionMode
) -> None:
    interval = settings.submission_min_interval_seconds
    if interval == 0:
        return
    try:
        accepted = await cache.set(
            f"rate:submission:user:{user_id}:{mode.value}", "1", nx=True, ex=interval
        )
    except Exception as exc:
        raise submission_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "RATE_LIMIT_UNAVAILABLE",
            "submission rate limit is temporarily unavailable",
        ) from exc
    if not accepted:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "SUBMISSION_RATE_LIMITED",
                "message": "submissions are too frequent; retry later",
            },
            headers={"Retry-After": str(interval)},
        )


def to_submission_public(submission: Submission) -> SubmissionPublic:
    return SubmissionPublic(
        id=submission.id,
        problem=SubmissionProblemPublic(
            id=submission.problem.id,
            slug=submission.problem.slug,
            title=submission.problem.title,
        ),
        language=SubmissionLanguagePublic(
            id=submission.language.id,
            slug=submission.language.slug,
            display_name=submission.language.display_name,
            version=submission.language.version,
        ),
        status=submission.status,
        mode=submission.mode,
        time_used_ms=submission.time_used_ms,
        memory_used_kb=submission.memory_used_kb,
        passed_case_count=submission.passed_case_count,
        total_case_count=submission.total_case_count,
        score=submission.score,
        judged_at=submission.judged_at,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
    )


def to_submission_created(submission: Submission, replay: bool) -> SubmissionCreated:
    return SubmissionCreated(
        **to_submission_public(submission).model_dump(), idempotent_replay=replay
    )


async def to_submission_detail(
    submission: Submission, object_store: SourceObjectStore, db: AsyncSession | None = None
) -> SubmissionDetail:
    if not submission.source_object_key:
        raise submission_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SOURCE_UNAVAILABLE",
            "submission source is temporarily unavailable",
        )
    try:
        source = await object_store.get_source(submission.source_object_key)
        source_code = source.decode("utf-8")
    except Exception as exc:
        raise submission_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SOURCE_UNAVAILABLE",
            "submission source is temporarily unavailable",
        ) from exc
    attempts: list[SubmissionAttemptPublic] = []
    if db is not None:
        rows = (
            await db.execute(
                select(SubmissionAttempt, SubmissionAttemptGroupResult, TestGroup)
                .outerjoin(
                    SubmissionAttemptGroupResult,
                    SubmissionAttemptGroupResult.attempt_id == SubmissionAttempt.id,
                )
                .outerjoin(TestGroup, TestGroup.id == SubmissionAttemptGroupResult.group_id)
                .where(SubmissionAttempt.submission_id == submission.id)
                .order_by(SubmissionAttempt.sequence, TestGroup.sequence)
            )
        ).all()
        by_attempt: dict[UUID, SubmissionAttemptPublic] = {}
        for attempt, group_result, group in rows:
            public = by_attempt.get(attempt.id)
            if public is None:
                public = SubmissionAttemptPublic(
                    sequence=attempt.sequence,
                    kind=attempt.kind,
                    status=attempt.status,
                    time_used_ms=attempt.time_used_ms,
                    memory_used_kb=attempt.memory_used_kb,
                    passed_case_count=attempt.passed_case_count,
                    total_case_count=attempt.total_case_count,
                    score=attempt.score,
                    judged_at=attempt.judged_at,
                )
                by_attempt[attempt.id] = public
            if group_result is not None and group is not None:
                public.groups.append(
                    SubmissionAttemptGroupPublic(
                        name=group.name,
                        sequence=group.sequence,
                        status=group_result.status,
                        score=group_result.score,
                        passed_case_count=group_result.passed_case_count,
                        total_case_count=group_result.total_case_count,
                        skipped=group_result.skipped,
                    )
                )
        attempts = list(by_attempt.values())
    return SubmissionDetail(
        **to_submission_public(submission).model_dump(),
        source_code=source_code,
        compiler_output=submission.compiler_output,
        error_message=submission.error_message,
        sample_output=(
            submission.sample_output
            if submission.mode in {SubmissionMode.SAMPLE, SubmissionMode.CUSTOM}
            else None
        ),
        attempts=attempts,
    )


async def create_submission(
    db: AsyncSession,
    cache: Redis,
    object_store: SourceObjectStore,
    user: User,
    problem_id: int,
    language_slug: str,
    source_code: str,
    mode: SubmissionMode,
    custom_input: str | None,
    idempotency_key: str | None,
) -> SubmissionCreated:
    key = normalize_idempotency_key(idempotency_key)
    content = source_code.encode("utf-8")
    if len(content) > settings.submission_source_max_bytes:
        raise submission_error(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "SOURCE_TOO_LARGE",
            f"source code exceeds {settings.submission_source_max_bytes} bytes",
        )

    custom_input_content = custom_input.encode("utf-8") if custom_input is not None else None
    if (
        custom_input_content is not None
        and len(custom_input_content) > settings.submission_custom_input_max_bytes
    ):
        raise submission_error(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "CUSTOM_INPUT_TOO_LARGE",
            f"custom input exceeds {settings.submission_custom_input_max_bytes} bytes",
        )

    checksum = hashlib.sha256(content).hexdigest()
    custom_input_checksum = (
        hashlib.sha256(custom_input_content).hexdigest()
        if custom_input_content is not None
        else None
    )
    request_fingerprint = _fingerprint(
        problem_id, language_slug, checksum, mode, custom_input_checksum
    )
    existing = await _find_idempotent_submission(db, user.id, key)
    if existing is not None:
        if existing.request_fingerprint != request_fingerprint:
            raise submission_error(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_KEY_REUSED",
                "Idempotency-Key was already used with a different request",
            )
        return to_submission_created(existing, replay=True)

    problem = await db.scalar(
        select(Problem).where(
            Problem.id == problem_id,
            Problem.visibility == ProblemVisibility.PUBLIC,
        )
    )
    if problem is None:
        raise submission_error(
            status.HTTP_404_NOT_FOUND, "PROBLEM_NOT_FOUND", "public problem not found"
        )
    language = await db.scalar(
        select(Language).where(
            Language.slug == language_slug,
            Language.slug.in_(settings.judge_supported_language_list),
            Language.enabled.is_(True),
        )
    )
    if language is None:
        raise submission_error(
            status.HTTP_400_BAD_REQUEST, "LANGUAGE_UNAVAILABLE", "language is not available"
        )

    active_test_set = None
    if mode is SubmissionMode.JUDGE:
        active_test_set = await db.scalar(
            select(TestSet).where(
                TestSet.problem_id == problem.id,
                TestSet.status == TestSetStatus.ACTIVE,
            )
        )
        if active_test_set is None:
            raise submission_error(
                status.HTTP_409_CONFLICT,
                "PROBLEM_NOT_READY",
                "problem has no active hidden test set",
            )

    await _enforce_submission_rate(cache, user.id, mode)

    user_id = user.id
    submission_id = uuid4()
    attempt_id = uuid4()
    object_key = (
        f"submissions/{user_id}/{datetime.now(timezone.utc):%Y/%m/%d}/"
        f"{submission_id}/{checksum}"
    )
    custom_input_object_key = (
        f"submission-inputs/{user_id}/{datetime.now(timezone.utc):%Y/%m/%d}/"
        f"{submission_id}/{custom_input_checksum}"
        if custom_input_checksum is not None
        else None
    )
    uploaded_keys: list[str] = []
    try:
        await object_store.put_source(object_key, content)
        uploaded_keys.append(object_key)
        if custom_input_object_key is not None and custom_input_content is not None:
            await object_store.put_source(custom_input_object_key, custom_input_content)
            uploaded_keys.append(custom_input_object_key)
    except Exception as exc:
        for uploaded_key in reversed(uploaded_keys):
            try:
                await object_store.delete_source(uploaded_key)
            except Exception:
                pass
        raise submission_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SOURCE_STORAGE_UNAVAILABLE",
            "source storage is temporarily unavailable",
        ) from exc

    submission = Submission(
        id=submission_id,
        user_id=user_id,
        problem=problem,
        language=language,
        status=SubmissionStatus.PENDING,
        mode=mode,
        test_set_id=active_test_set.id if active_test_set is not None else None,
        problem_version=problem.version,
        time_limit_ms_snapshot=problem.time_limit_ms,
        memory_limit_mb_snapshot=problem.memory_limit_mb,
        source_code=None,
        source_object_key=object_key,
        source_checksum=checksum,
        custom_input_object_key=custom_input_object_key,
        custom_input_checksum=custom_input_checksum,
        custom_input_size_bytes=(
            len(custom_input_content) if custom_input_content is not None else None
        ),
        idempotency_key=key,
        request_fingerprint=request_fingerprint,
        effective_attempt_id=attempt_id,
    )
    attempt = SubmissionAttempt(
        id=attempt_id,
        submission_id=submission_id,
        sequence=1,
        kind="initial",
        status=SubmissionStatus.PENDING,
        problem_id=problem.id,
        test_set_id=active_test_set.id if active_test_set is not None else None,
        problem_version=problem.version,
        time_limit_ms_snapshot=problem.time_limit_ms,
        memory_limit_mb_snapshot=problem.memory_limit_mb,
    )
    event_id = uuid4()
    event = Outbox(
        id=event_id,
        aggregate_type="submission",
        aggregate_id=submission_id,
        event_type="submission.created",
        payload={
            "event_id": str(event_id),
            "submission_id": str(submission_id),
        },
    )
    db.add(submission)
    try:
        # submission_attempts has an immediate FK back to submissions, while
        # submissions.effective_attempt_id is deferred. Establish the parent
        # row first so PostgreSQL cannot choose an invalid flush order.
        await db.flush()
        db.add_all([attempt, event])
        await db.commit()
    except IntegrityError:
        await db.rollback()
        for uploaded_key in reversed(uploaded_keys):
            try:
                await object_store.delete_source(uploaded_key)
            except Exception:
                pass
        winner = await _find_idempotent_submission(db, user_id, key)
        if winner is not None and winner.request_fingerprint == request_fingerprint:
            return to_submission_created(winner, replay=True)
        raise submission_error(
            status.HTTP_409_CONFLICT,
            "IDEMPOTENCY_CONFLICT",
            "submission could not be created because of a concurrent request",
        ) from None
    except Exception:
        await db.rollback()
        # A lost connection can make commit outcome ambiguous. Preserve the immutable object
        # so a transaction that did commit never points to deleted source; lifecycle cleanup
        # handles the safer failure mode (an unreferenced object).
        raise
    return to_submission_created(submission, replay=False)


async def get_owned_submission(
    db: AsyncSession, submission_id: UUID, user_id: UUID
) -> Submission | None:
    return await db.scalar(
        select(Submission)
        .options(joinedload(Submission.problem), joinedload(Submission.language))
        .where(Submission.id == submission_id, Submission.user_id == user_id)
    )


async def list_owned_submissions(
    db: AsyncSession,
    user_id: UUID,
    page: int,
    page_size: int,
    problem_id: int | None,
    language_slug: str | None = None,
    submission_status: SubmissionStatus | None = None,
    mode: SubmissionMode | None = None,
) -> SubmissionPage:
    filters = [Submission.user_id == user_id]
    if problem_id is not None:
        filters.append(Submission.problem_id == problem_id)
    if language_slug is not None:
        filters.append(Language.slug == language_slug)
    if submission_status is not None:
        filters.append(Submission.status == submission_status)
    if mode is not None:
        filters.append(Submission.mode == mode)
    total = (
        await db.scalar(
            select(func.count(Submission.id))
            .join(Language, Submission.language_id == Language.id)
            .where(*filters)
        )
        or 0
    )
    items = (
        await db.scalars(
            select(Submission)
            .join(Language, Submission.language_id == Language.id)
            .options(joinedload(Submission.problem), joinedload(Submission.language))
            .where(*filters)
            .order_by(Submission.created_at.desc(), Submission.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return SubmissionPage(
        items=[to_submission_public(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )


TERMINAL_STATUSES = frozenset(
    {
        SubmissionStatus.ACCEPTED,
        SubmissionStatus.WRONG_ANSWER,
        SubmissionStatus.COMPILE_ERROR,
        SubmissionStatus.RUNTIME_ERROR,
        SubmissionStatus.TIME_LIMIT_EXCEEDED,
        SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
        SubmissionStatus.OUTPUT_LIMIT_EXCEEDED,
        SubmissionStatus.SYSTEM_ERROR,
    }
)
ALLOWED_STATUS_TRANSITIONS = {
    SubmissionStatus.PENDING: frozenset({SubmissionStatus.COMPILING}),
    SubmissionStatus.COMPILING: frozenset(
        {
            SubmissionStatus.RUNNING,
            SubmissionStatus.COMPILE_ERROR,
            SubmissionStatus.SYSTEM_ERROR,
        }
    ),
    SubmissionStatus.RUNNING: frozenset(
        {
            SubmissionStatus.ACCEPTED,
            SubmissionStatus.WRONG_ANSWER,
            SubmissionStatus.RUNTIME_ERROR,
            SubmissionStatus.TIME_LIMIT_EXCEEDED,
            SubmissionStatus.MEMORY_LIMIT_EXCEEDED,
            SubmissionStatus.OUTPUT_LIMIT_EXCEEDED,
            SubmissionStatus.SYSTEM_ERROR,
        }
    ),
}


class InvalidSubmissionTransition(ValueError):
    pass


def transition_submission_status(
    submission: Submission, next_status: SubmissionStatus
) -> None:
    if next_status == submission.status:
        return
    if next_status not in ALLOWED_STATUS_TRANSITIONS.get(submission.status, frozenset()):
        raise InvalidSubmissionTransition(f"{submission.status.value} -> {next_status.value}")
    submission.status = next_status
    if next_status in TERMINAL_STATUSES:
        submission.judged_at = datetime.now(timezone.utc)
