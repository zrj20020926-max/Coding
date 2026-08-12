from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import inspect
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
    DailyChallengeAdminPage,
    DailyChallengePublic,
    DailyChallengeSet,
)
from app.services.audit import record_audit
from app.services.collections import (
    create_collection,
    delete_daily_challenge,
    get_admin_collection,
    list_admin_collections,
    list_daily_challenges,
    reorder_collection,
    set_collection_public,
    set_daily_challenge,
    update_collection,
)

router = APIRouter(prefix="/admin", tags=["内容运营管理"])


async def audit_content(
    db: AsyncSession,
    admin: User,
    action: str,
    target_type: str,
    target_id: int | date,
    metadata: dict | None = None,
) -> None:
    actor_id = inspect(admin).identity[0]
    record_audit(
        db,
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=actor_id,
        metadata=metadata,
    )
    await db.commit()


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
    result = await create_collection(db, payload, admin.id)
    await audit_content(db, admin, "collection.create", "collection", result.id)
    return result


@router.patch("/collections/{collection_id}", response_model=AdminCollection)
async def edit_collection(
    collection_id: int,
    payload: CollectionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> AdminCollection:
    result = await update_collection(db, collection_id, payload)
    await audit_content(db, admin, "collection.update", "collection", collection_id)
    return result


@router.put("/collections/{collection_id}/problems", response_model=AdminCollection)
async def order_collection_problems(
    collection_id: int,
    payload: CollectionOrderUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> AdminCollection:
    result = await reorder_collection(db, collection_id, payload.problem_ids)
    await audit_content(
        db,
        admin,
        "collection.reorder",
        "collection",
        collection_id,
        {"problem_count": len(payload.problem_ids)},
    )
    return result


@router.post("/collections/{collection_id}/publish", response_model=AdminCollection)
async def publish_collection(
    collection_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> AdminCollection:
    result = await set_collection_public(db, collection_id, True)
    await audit_content(db, admin, "collection.publish", "collection", collection_id)
    return result


@router.post("/collections/{collection_id}/offline", response_model=AdminCollection)
async def offline_collection(
    collection_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> AdminCollection:
    result = await set_collection_public(db, collection_id, False)
    await audit_content(db, admin, "collection.offline", "collection", collection_id)
    return result


@router.get("/daily-challenges", response_model=DailyChallengeAdminPage)
async def get_admin_daily_challenges(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
    start_date: date,
    end_date: date,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DailyChallengeAdminPage:
    return await list_daily_challenges(db, start_date, end_date, page, page_size)


@router.put("/daily-challenges/{challenge_date}", response_model=DailyChallengePublic)
async def put_daily_challenge(
    challenge_date: date,
    payload: DailyChallengeSet,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> DailyChallengePublic:
    result = await set_daily_challenge(db, challenge_date, payload.problem_id)
    await audit_content(
        db,
        admin,
        "daily_challenge.set",
        "daily_challenge",
        challenge_date,
        {"problem_id": payload.problem_id},
    )
    return result


@router.delete(
    "/daily-challenges/{challenge_date}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_daily_challenge(
    challenge_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> None:
    await delete_daily_challenge(db, challenge_date)
    await audit_content(
        db, admin, "daily_challenge.delete", "daily_challenge", challenge_date
    )
