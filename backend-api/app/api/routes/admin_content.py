from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.content import (
    AdminCollection,
    AdminCollectionPage,
    CollectionCreate,
    CollectionOrderUpdate,
    CollectionUpdate,
    DailyChallengePublic,
    DailyChallengeSet,
)
from app.services.collections import (
    create_collection,
    get_admin_collection,
    list_admin_collections,
    reorder_collection,
    set_collection_public,
    set_daily_challenge,
    update_collection,
)

router = APIRouter(prefix="/admin", tags=["内容运营管理"])


@router.get("/collections", response_model=AdminCollectionPage)
async def get_admin_collections(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminCollectionPage:
    return await list_admin_collections(db, page, page_size)


@router.get("/collections/{collection_id}", response_model=AdminCollection)
async def get_admin_collection_detail(
    collection_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminCollection:
    return await get_admin_collection(db, collection_id)


@router.post(
    "/collections",
    response_model=AdminCollection,
    status_code=status.HTTP_201_CREATED,
)
async def add_collection(
    payload: CollectionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> AdminCollection:
    return await create_collection(db, payload, admin.id)


@router.patch("/collections/{collection_id}", response_model=AdminCollection)
async def edit_collection(
    collection_id: int,
    payload: CollectionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminCollection:
    return await update_collection(db, collection_id, payload)


@router.put("/collections/{collection_id}/problems", response_model=AdminCollection)
async def order_collection_problems(
    collection_id: int,
    payload: CollectionOrderUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminCollection:
    return await reorder_collection(db, collection_id, payload.problem_ids)


@router.post("/collections/{collection_id}/publish", response_model=AdminCollection)
async def publish_collection(
    collection_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminCollection:
    return await set_collection_public(db, collection_id, True)


@router.post("/collections/{collection_id}/offline", response_model=AdminCollection)
async def offline_collection(
    collection_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminCollection:
    return await set_collection_public(db, collection_id, False)


@router.put("/daily-challenges/{challenge_date}", response_model=DailyChallengePublic)
async def put_daily_challenge(
    challenge_date: date,
    payload: DailyChallengeSet,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> DailyChallengePublic:
    return await set_daily_challenge(db, challenge_date, payload.problem_id)
