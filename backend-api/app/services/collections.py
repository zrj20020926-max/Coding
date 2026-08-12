from __future__ import annotations

import math
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.content import Collection, CollectionProblem, DailyChallenge
from app.models.problem import (
    Favorite,
    Problem,
    ProblemTag,
    ProblemVisibility,
    UserProblemProgress,
)
from app.schemas.content import (
    AdminCollection,
    AdminCollectionPage,
    AdminCollectionSummary,
    CollectionCreate,
    CollectionDetail,
    CollectionPage,
    CollectionProblemPublic,
    CollectionSummary,
    CollectionUpdate,
    DailyChallengeAdminItem,
    DailyChallengeAdminPage,
    DailyChallengePublic,
)
from app.services.problems import to_problem_summary


def content_error(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"code": code, "message": message},
    )


def collection_options() -> list[object]:
    return [selectinload(Collection.items).selectinload(CollectionProblem.problem)]


async def _personal_maps(
    db: AsyncSession, user_id: UUID | None, problem_ids: list[int]
) -> tuple[dict[int, UserProblemProgress], set[int]]:
    if user_id is None or not problem_ids:
        return {}, set()
    progress = (
        await db.scalars(
            select(UserProblemProgress).where(
                UserProblemProgress.user_id == user_id,
                UserProblemProgress.problem_id.in_(problem_ids),
            )
        )
    ).all()
    favorites = set(
        (
            await db.scalars(
                select(Favorite.problem_id).where(
                    Favorite.user_id == user_id,
                    Favorite.problem_id.in_(problem_ids),
                )
            )
        ).all()
    )
    return {item.problem_id: item for item in progress}, favorites


def _public_items(collection: Collection) -> list[CollectionProblem]:
    return [
        item
        for item in sorted(collection.items, key=lambda candidate: candidate.sequence)
        if item.problem.visibility is ProblemVisibility.PUBLIC
    ]


async def list_public_collections(
    db: AsyncSession,
    user_id: UUID | None,
    page: int,
    page_size: int,
) -> CollectionPage:
    total = int(
        await db.scalar(select(func.count(Collection.id)).where(Collection.is_public.is_(True)))
        or 0
    )
    collections = (
        await db.scalars(
            select(Collection)
            .where(Collection.is_public.is_(True))
            .options(*collection_options())
            .order_by(Collection.created_at.desc(), Collection.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    problem_ids = [
        item.problem_id
        for collection in collections
        for item in _public_items(collection)
    ]
    progress, _ = await _personal_maps(db, user_id, problem_ids)
    return CollectionPage(
        items=[
            CollectionSummary(
                id=collection.id,
                slug=collection.slug,
                title=collection.title,
                description=collection.description,
                company=collection.company,
                cover_url=collection.cover_url,
                problem_count=len(_public_items(collection)),
                solved_count=(
                    sum(
                        bool(progress.get(item.problem_id) and progress[item.problem_id].accepted)
                        for item in _public_items(collection)
                    )
                    if user_id is not None
                    else None
                ),
            )
            for collection in collections
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def _load_collection(
    db: AsyncSession, *, slug: str | None = None, collection_id: int | None = None
) -> Collection | None:
    statement = select(Collection).options(*collection_options())
    if slug is not None:
        statement = statement.where(Collection.slug == slug)
    if collection_id is not None:
        statement = statement.where(Collection.id == collection_id)
    return await db.scalar(statement)


async def list_admin_collections(
    db: AsyncSession,
    page: int,
    page_size: int,
) -> AdminCollectionPage:
    total = int(await db.scalar(select(func.count(Collection.id))) or 0)
    collections = (
        await db.scalars(
            select(Collection)
            .options(*collection_options())
            .order_by(Collection.created_at.desc(), Collection.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return AdminCollectionPage(
        items=[
            AdminCollectionSummary(
                id=collection.id,
                slug=collection.slug,
                title=collection.title,
                description=collection.description,
                company=collection.company,
                cover_url=collection.cover_url,
                problem_count=len(collection.items),
                solved_count=None,
                is_public=collection.is_public,
            )
            for collection in collections
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def get_public_collection(
    db: AsyncSession,
    slug: str,
    user_id: UUID | None,
    page: int,
    page_size: int,
) -> CollectionDetail:
    collection = await _load_collection(db, slug=slug)
    if collection is None or not collection.is_public:
        raise content_error(404, "COLLECTION_NOT_FOUND", "公开题单不存在")
    all_items = _public_items(collection)
    selected = all_items[(page - 1) * page_size : page * page_size]
    progress, favorites = await _personal_maps(
        db, user_id, [item.problem_id for item in all_items]
    )
    return CollectionDetail(
        id=collection.id,
        slug=collection.slug,
        title=collection.title,
        description=collection.description,
        company=collection.company,
        cover_url=collection.cover_url,
        problem_count=len(all_items),
        solved_count=(
            sum(
                bool(
                    progress.get(item.problem_id)
                    and progress[item.problem_id].accepted
                )
                for item in all_items
            )
            if user_id is not None
            else None
        ),
        problems=[
            CollectionProblemPublic(
                sequence=item.sequence,
                problem=to_problem_summary(
                    item.problem,
                    progress.get(item.problem_id),
                    authenticated=user_id is not None,
                    favorited=item.problem_id in favorites,
                ),
            )
            for item in selected
        ],
        page=page,
        page_size=page_size,
        pages=math.ceil(len(all_items) / page_size) if all_items else 0,
    )


async def _validate_problem_ids(db: AsyncSession, problem_ids: list[int]) -> list[Problem]:
    if not problem_ids:
        return []
    problems = (await db.scalars(select(Problem).where(Problem.id.in_(problem_ids)))).all()
    by_id = {problem.id: problem for problem in problems}
    missing = [problem_id for problem_id in problem_ids if problem_id not in by_id]
    if missing:
        raise content_error(
            status.HTTP_400_BAD_REQUEST,
            "UNKNOWN_PROBLEM",
            f"题目不存在: {', '.join(map(str, missing))}",
        )
    return [by_id[problem_id] for problem_id in problem_ids]


async def _replace_items(
    db: AsyncSession, collection: Collection, problem_ids: list[int]
) -> None:
    await _validate_problem_ids(db, problem_ids)
    await db.execute(
        delete(CollectionProblem).where(CollectionProblem.collection_id == collection.id)
    )
    await db.flush()
    db.add_all(
        [
            CollectionProblem(
                collection_id=collection.id,
                problem_id=problem_id,
                sequence=sequence,
            )
            for sequence, problem_id in enumerate(problem_ids)
        ]
    )


async def _save_collection(db: AsyncSession, collection: Collection) -> Collection:
    collection_id = collection.id
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise content_error(409, "COLLECTION_CONFLICT", "题单标识或题目顺序冲突") from None
    db.expire_all()
    loaded = await _load_collection(db, collection_id=collection_id)
    if loaded is None:  # pragma: no cover
        raise content_error(404, "COLLECTION_NOT_FOUND", "题单不存在")
    return loaded


async def _to_admin_collection(db: AsyncSession, collection: Collection) -> AdminCollection:
    items = sorted(collection.items, key=lambda candidate: candidate.sequence)
    return AdminCollection(
        id=collection.id,
        slug=collection.slug,
        title=collection.title,
        description=collection.description,
        company=collection.company,
        cover_url=collection.cover_url,
        problem_count=len(items),
        solved_count=None,
        problems=[
            CollectionProblemPublic(
                sequence=item.sequence,
                problem=to_problem_summary(item.problem, None, authenticated=False),
            )
            for item in items
        ],
        page=1,
        page_size=max(1, len(items)),
        pages=1 if items else 0,
        is_public=collection.is_public,
    )


async def get_admin_collection(
    db: AsyncSession, collection_id: int
) -> AdminCollection:
    collection = await _load_collection(db, collection_id=collection_id)
    if collection is None:
        raise content_error(404, "COLLECTION_NOT_FOUND", "题单不存在")
    return await _to_admin_collection(db, collection)


async def create_collection(
    db: AsyncSession, payload: CollectionCreate, admin_id: UUID
) -> AdminCollection:
    collection = Collection(
        **payload.model_dump(exclude={"problem_ids"}),
        is_public=False,
        created_by=admin_id,
    )
    db.add(collection)
    await db.flush()
    await _replace_items(db, collection, payload.problem_ids)
    return await _to_admin_collection(db, await _save_collection(db, collection))


async def update_collection(
    db: AsyncSession, collection_id: int, payload: CollectionUpdate
) -> AdminCollection:
    collection = await _load_collection(db, collection_id=collection_id)
    if collection is None:
        raise content_error(404, "COLLECTION_NOT_FOUND", "题单不存在")
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(collection, name, value)
    return await _to_admin_collection(db, await _save_collection(db, collection))


async def reorder_collection(
    db: AsyncSession, collection_id: int, problem_ids: list[int]
) -> AdminCollection:
    collection = await _load_collection(db, collection_id=collection_id)
    if collection is None:
        raise content_error(404, "COLLECTION_NOT_FOUND", "题单不存在")
    try:
        await _replace_items(db, collection, problem_ids)
        return await _to_admin_collection(db, await _save_collection(db, collection))
    except Exception:
        await db.rollback()
        raise


async def set_collection_public(
    db: AsyncSession, collection_id: int, is_public: bool
) -> AdminCollection:
    collection = await _load_collection(db, collection_id=collection_id)
    if collection is None:
        raise content_error(404, "COLLECTION_NOT_FOUND", "题单不存在")
    collection.is_public = is_public
    return await _to_admin_collection(db, await _save_collection(db, collection))


def current_content_date() -> date:
    return datetime.now(ZoneInfo(settings.content_timezone)).date()


async def get_daily_challenge(
    db: AsyncSession, user_id: UUID | None
) -> DailyChallengePublic:
    challenge_date = current_content_date()
    challenge = await db.scalar(
        select(DailyChallenge).where(DailyChallenge.challenge_date == challenge_date)
    )
    if challenge is None or challenge.problem.visibility is not ProblemVisibility.PUBLIC:
        raise content_error(404, "DAILY_CHALLENGE_NOT_FOUND", "今日题目尚未发布")
    progress, favorites = await _personal_maps(db, user_id, [challenge.problem_id])
    return DailyChallengePublic(
        challenge_date=challenge_date,
        timezone=settings.content_timezone,
        problem=to_problem_summary(
            challenge.problem,
            progress.get(challenge.problem_id),
            authenticated=user_id is not None,
            favorited=challenge.problem_id in favorites,
        ),
    )


async def set_daily_challenge(
    db: AsyncSession, challenge_date: date, problem_id: int
) -> DailyChallengePublic:
    problem = await db.scalar(
        select(Problem)
        .where(Problem.id == problem_id)
        .options(selectinload(Problem.tag_links).selectinload(ProblemTag.tag))
    )
    if problem is None:
        raise content_error(400, "UNKNOWN_PROBLEM", "题目不存在")
    challenge = await db.get(DailyChallenge, challenge_date)
    if challenge is None:
        challenge = DailyChallenge(challenge_date=challenge_date, problem_id=problem_id)
        db.add(challenge)
    else:
        challenge.problem_id = problem_id
    await db.commit()
    return DailyChallengePublic(
        challenge_date=challenge_date,
        timezone=settings.content_timezone,
        problem=to_problem_summary(problem, None, authenticated=False),
    )


async def list_daily_challenges(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    page: int,
    page_size: int,
) -> DailyChallengeAdminPage:
    if start_date > end_date:
        raise content_error(400, "INVALID_DATE_RANGE", "开始日期不能晚于结束日期")
    filters = [
        DailyChallenge.challenge_date >= start_date,
        DailyChallenge.challenge_date <= end_date,
    ]
    total = int(
        await db.scalar(select(func.count(DailyChallenge.challenge_date)).where(*filters))
        or 0
    )
    rows = (
        await db.scalars(
            select(DailyChallenge)
            .where(*filters)
            .order_by(DailyChallenge.challenge_date.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return DailyChallengeAdminPage(
        items=[
            DailyChallengeAdminItem(
                challenge_date=row.challenge_date,
                timezone=settings.content_timezone,
                problem=to_problem_summary(row.problem, None, authenticated=False),
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def delete_daily_challenge(db: AsyncSession, challenge_date: date) -> None:
    challenge = await db.get(DailyChallenge, challenge_date)
    if challenge is None:
        raise content_error(404, "DAILY_CHALLENGE_NOT_FOUND", "每日一题不存在")
    await db.delete(challenge)
    await db.commit()
