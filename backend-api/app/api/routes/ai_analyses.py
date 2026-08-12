from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, get_redis_client
from app.models.user import User
from app.schemas.ai import AIAnalysisPublic, AIAnalysisTriggered
from app.services.ai_analyses import ai_error, get_owned_analysis, to_ai_public, trigger_analysis

router = APIRouter(prefix="/submissions", tags=["ai-analysis"])


@router.post(
    "/{submission_id}/ai-analysis",
    response_model=AIAnalysisTriggered,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request an isolated AI review of an owned failed submission",
)
async def request_ai_analysis(
    submission_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    cache: Annotated[Redis, Depends(get_redis_client)],
    current_user: Annotated[User, Depends(get_current_user)],
    request_id: Annotated[
        Optional[str],
        Header(alias="X-Request-Id", max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$"),
    ] = None,
) -> AIAnalysisTriggered:
    return await trigger_analysis(db, cache, submission_id, current_user.id, request_id)


@router.get(
    "/{submission_id}/ai-analysis",
    response_model=AIAnalysisPublic,
    summary="Get an owned submission's AI analysis",
)
async def get_ai_analysis(
    submission_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AIAnalysisPublic:
    analysis = await get_owned_analysis(db, submission_id, current_user.id)
    if analysis is None:
        raise ai_error(status.HTTP_404_NOT_FOUND, "AI_ANALYSIS_NOT_FOUND", "AI analysis not found")
    return to_ai_public(analysis)
