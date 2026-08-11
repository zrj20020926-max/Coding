from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.content import CollectionDetail, CollectionPage, DailyChallengePublic
from app.services.collections import (
    get_daily_challenge,
    get_public_collection,
    list_public_collections,
)

router = APIRouter(tags=["内容运营"])


@router.get("/collections", response_model=CollectionPage)
async def get_collections(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CollectionPage:
    return await list_public_collections(
        db,
        current_user.id if current_user else None,
        page,
        page_size,
    )


@router.get("/collections/{slug}", response_model=CollectionDetail)
async def get_collection(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CollectionDetail:
    return await get_public_collection(
        db,
        slug,
        current_user.id if current_user else None,
        page,
        page_size,
    )


@router.get(
    "/daily-challenge",
    response_model=DailyChallengePublic,
    response_model_exclude_none=True,
)
async def get_today_challenge(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
) -> DailyChallengePublic:
    return await get_daily_challenge(db, current_user.id if current_user else None)
