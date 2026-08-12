from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_admin_user
from app.db.session import get_db
from app.models.problem import Problem, ProblemTag, ProblemVisibility, Tag, TestSet, TestSetStatus
from app.models.user import User
from app.schemas.problem import AdminProblem, ProblemCreate, ProblemUpdate
from app.schemas.test_set import (
    TestCaseAdminPublic,
    TestCaseCreate,
    TestSetAdminPublic,
    TestSetCreate,
    TestSetValidationPublic,
)
from app.services.object_storage import SourceObjectStore, get_source_object_store
from app.services.problems import get_problem_with_tags, to_admin_problem
from app.services.test_sets import (
    activate_test_set,
    add_test_case,
    create_test_set,
    delete_test_set,
    list_test_sets,
    test_set_error,
    validate_and_mark,
    validate_test_set,
)

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
    if payload.visibility is ProblemVisibility.PUBLIC:
        raise test_set_error(
            status.HTTP_409_CONFLICT,
            "PROBLEM_NOT_READY",
            "题目必须在激活有效测试集后发布",
            [],
        )
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
    versioned_fields = {
        "title",
        "description",
        "difficulty",
        "input_description",
        "output_description",
        "sample_input",
        "sample_output",
        "time_limit_ms",
        "memory_limit_mb",
    }
    if any(
        field_name in versioned_fields and getattr(problem, field_name) != value
        for field_name, value in values.items()
    ):
        problem.version += 1
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
    object_store: Annotated[SourceObjectStore, Depends(get_source_object_store)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminProblem:
    problem = await db.scalar(
        select(Problem).where(Problem.id == problem_id).with_for_update()
    )
    if problem is None:
        raise admin_problem_not_found()
    active = await db.scalar(
        select(TestSet)
        .where(TestSet.problem_id == problem_id, TestSet.status == TestSetStatus.ACTIVE)
        .with_for_update()
    )
    if active is None:
        raise test_set_error(
            status.HTTP_409_CONFLICT,
            "PROBLEM_NOT_READY",
            "题目缺少有效的隐藏测试集",
            [],
        )
    # Reload cases for the validation gate without ever serializing internal fields.
    validation = await validate_and_mark_for_publish(db, active, object_store)
    if validation:
        raise test_set_error(
            status.HTTP_409_CONFLICT,
            "PROBLEM_NOT_READY",
            "题目未通过发布校验",
            validation,
        )
    return await set_visibility(problem_id, ProblemVisibility.PUBLIC, db)


@router.post("/{problem_id}/offline", response_model=AdminProblem)
async def offline_problem(
    problem_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminProblem:
    return await set_visibility(problem_id, ProblemVisibility.PRIVATE, db)


async def validate_and_mark_for_publish(
    db: AsyncSession, active: TestSet, object_store: SourceObjectStore
) -> list:
    # Avoid changing an active set's status during a publication re-check.
    loaded = await db.scalar(
        select(TestSet)
        .options(selectinload(TestSet.cases))
        .where(TestSet.id == active.id)
    )
    assert loaded is not None
    return await validate_test_set(db, loaded, object_store)


@router.get("/{problem_id}/test-sets", response_model=list[TestSetAdminPublic])
async def get_problem_test_sets(
    problem_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> list[TestSetAdminPublic]:
    return await list_test_sets(db, problem_id)


@router.post(
    "/{problem_id}/test-sets",
    response_model=TestSetAdminPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_problem_test_set(
    problem_id: int,
    payload: TestSetCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(get_admin_user)],
) -> TestSetAdminPublic:
    return await create_test_set(db, problem_id, current_admin.id, payload)


@router.post(
    "/test-sets/{test_set_id}/cases",
    response_model=TestCaseAdminPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_test_set_case(
    test_set_id: UUID,
    payload: TestCaseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    object_store: Annotated[SourceObjectStore, Depends(get_source_object_store)],
    _: Annotated[User, Depends(get_admin_user)],
) -> TestCaseAdminPublic:
    return await add_test_case(db, test_set_id, payload, object_store)


@router.post(
    "/test-sets/{test_set_id}/validate",
    response_model=TestSetValidationPublic,
)
async def validate_admin_test_set(
    test_set_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    object_store: Annotated[SourceObjectStore, Depends(get_source_object_store)],
    _: Annotated[User, Depends(get_admin_user)],
) -> TestSetValidationPublic:
    return await validate_and_mark(db, test_set_id, object_store)


@router.post(
    "/test-sets/{test_set_id}/activate",
    response_model=TestSetAdminPublic,
)
async def activate_admin_test_set(
    test_set_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    object_store: Annotated[SourceObjectStore, Depends(get_source_object_store)],
    _: Annotated[User, Depends(get_admin_user)],
) -> TestSetAdminPublic:
    return await activate_test_set(db, test_set_id, object_store)


@router.delete(
    "/test-sets/{test_set_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_admin_test_set(
    test_set_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> None:
    await delete_test_set(db, test_set_id)
