from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user
from app.db.session import get_db
from app.models.problem import Problem, ProblemTag, ProblemVisibility, Tag
from app.models.user import User
from app.schemas.problem import AdminProblem, ProblemCreate, ProblemUpdate
from app.services.problems import get_problem_with_tags, to_admin_problem

router = APIRouter(prefix="/admin/problems", tags=["题库管理"])


def admin_problem_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "PROBLEM_NOT_FOUND", "message": "题目不存在"},
    )


def conflict(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "PROBLEM_CONFLICT", "message": message},
    )


async def resolve_tags(db: AsyncSession, tag_slugs: list[str]) -> list[Tag]:
    if not tag_slugs:
        return []
    tags = (
        await db.scalars(select(Tag).where(Tag.slug.in_(tag_slugs)).order_by(Tag.id.asc()))
    ).all()
    found = {tag.slug for tag in tags}
    missing = sorted(set(tag_slugs) - found)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNKNOWN_TAG",
                "message": f"未知标签: {', '.join(missing)}",
            },
        )
    tags_by_slug = {tag.slug: tag for tag in tags}
    return [tags_by_slug[slug] for slug in tag_slugs]


async def save_problem(db: AsyncSession, problem: Problem) -> AdminProblem:
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise conflict("题目标识已存在") from None
    loaded = await get_problem_with_tags(db, problem.id, public_only=False)
    if loaded is None:  # pragma: no cover - committed row cannot disappear in normal operation
        raise admin_problem_not_found()
    return to_admin_problem(loaded)


def replace_problem_tags(problem: Problem, tags: list[Tag]) -> None:
    existing = {link.tag.slug: link for link in problem.tag_links}
    links: list[ProblemTag] = []
    for tag in tags:
        link = existing.get(tag.slug)
        links.append(link if link is not None else ProblemTag(tag=tag))
    problem.tag_links = links


@router.post("", response_model=AdminProblem, status_code=status.HTTP_201_CREATED)
async def create_problem(
    payload: ProblemCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(get_admin_user)],
) -> AdminProblem:
    tags = await resolve_tags(db, payload.tag_slugs)
    values = payload.model_dump(exclude={"tag_slugs"})
    problem = Problem(**values, created_by=current_admin.id)
    problem.tag_links = [ProblemTag(tag=tag) for tag in tags]
    db.add(problem)
    return await save_problem(db, problem)


@router.patch("/{problem_id}", response_model=AdminProblem)
async def update_problem(
    problem_id: int,
    payload: ProblemUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminProblem:
    problem = await get_problem_with_tags(db, problem_id, public_only=False)
    if problem is None:
        raise admin_problem_not_found()
    values = payload.model_dump(exclude_unset=True)
    tag_slugs = values.pop("tag_slugs", None)
    for field_name, value in values.items():
        setattr(problem, field_name, value)
    if tag_slugs is not None:
        tags = await resolve_tags(db, tag_slugs)
        replace_problem_tags(problem, tags)
    return await save_problem(db, problem)


async def set_visibility(
    problem_id: int,
    visibility: ProblemVisibility,
    db: AsyncSession,
) -> AdminProblem:
    problem = await get_problem_with_tags(db, problem_id, public_only=False)
    if problem is None:
        raise admin_problem_not_found()
    problem.visibility = visibility
    return await save_problem(db, problem)


@router.post("/{problem_id}/publish", response_model=AdminProblem)
async def publish_problem(
    problem_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminProblem:
    return await set_visibility(problem_id, ProblemVisibility.PUBLIC, db)


@router.post("/{problem_id}/offline", response_model=AdminProblem)
async def offline_problem(
    problem_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminProblem:
    return await set_visibility(problem_id, ProblemVisibility.PRIVATE, db)
