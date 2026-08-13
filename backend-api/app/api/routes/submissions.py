from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, get_redis_client
from app.models.submission import SubmissionMode, SubmissionStatus
from app.models.user import User
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionCreated,
    SubmissionDetail,
    SubmissionPage,
    SubmissionPublic,
)
from app.services.object_storage import SourceObjectStore, get_source_object_store
from app.services.submissions import (
    create_submission,
    get_owned_submission,
    list_owned_submissions,
    submission_error,
    to_submission_detail,
    to_submission_public,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post(
    "",
    response_model=SubmissionCreated,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reliably accept and enqueue a source submission",
)
async def submit_source(
    payload: SubmissionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
    object_store: Annotated[SourceObjectStore, Depends(get_source_object_store)],
    current_user: Annotated[User, Depends(get_current_user)],
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
) -> SubmissionCreated:
    return await create_submission(
        db,
        cache,
        object_store,
        current_user,
        payload.problem_id,
        payload.language,
        payload.source_code,
        payload.mode,
        idempotency_key,
    )


@router.get("", response_model=SubmissionPage, summary="List the current user's submissions")
async def get_my_submissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    problem_id: Annotated[Optional[int], Query(gt=0)] = None,
    language: Annotated[Optional[str], Query(min_length=1, max_length=30)] = None,
    submission_status: Annotated[
        Optional[SubmissionStatus], Query(alias="status")
    ] = None,
    mode: Annotated[Optional[SubmissionMode], Query()] = None,
) -> SubmissionPage:
    return await list_owned_submissions(
        db,
        current_user.id,
        page,
        page_size,
        problem_id,
        language,
        submission_status,
        mode,
    )


@router.get(
    "/{submission_id}/status",
    response_model=SubmissionPublic,
    summary="Poll a current-user-owned submission status",
)
async def get_my_submission_status(
    submission_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SubmissionPublic:
    submission = await get_owned_submission(db, submission_id, current_user.id)
    if submission is None:
        raise submission_error(
            status.HTTP_404_NOT_FOUND, "SUBMISSION_NOT_FOUND", "submission not found"
        )
    return to_submission_public(submission)


@router.get(
    "/{submission_id}",
    response_model=SubmissionDetail,
    summary="Get a current-user-owned submission",
)
async def get_my_submission(
    submission_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    object_store: Annotated[SourceObjectStore, Depends(get_source_object_store)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SubmissionDetail:
    submission = await get_owned_submission(db, submission_id, current_user.id)
    if submission is None:
        # Returning the same 404 for missing and foreign records avoids leaking ownership.
        raise submission_error(
            status.HTTP_404_NOT_FOUND, "SUBMISSION_NOT_FOUND", "submission not found"
        )
    return await to_submission_detail(submission, object_store)
