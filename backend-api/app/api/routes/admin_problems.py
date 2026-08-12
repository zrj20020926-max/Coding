from __future__ import annotations

# ruff: noqa: UP045
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import exists, func, literal, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_admin_user
from app.core.config import settings
from app.db.session import get_db
from app.models.problem import (
    Problem,
    ProblemDifficulty,
    ProblemTag,
    ProblemVisibility,
    Tag,
    TestSet,
    TestSetStatus,
)
from app.models.user import User
from app.schemas.problem import (
    AdminProblem,
    AdminProblemPage,
    AdminProblemSort,
    ProblemCreate,
    ProblemUpdate,
)
from app.schemas.test_set import (
    ProblemReadinessPublic,
    TestCaseAdminPublic,
    TestCaseBatchUploadPublic,
    TestCaseCreate,
    TestSetAdminPublic,
    TestSetCreate,
    TestSetValidationPublic,
)
from app.services.audit import record_audit
from app.services.object_storage import SourceObjectStore, get_source_object_store
from app.services.problems import get_problem_with_tags, to_admin_problem
from app.services.test_data_uploads import upload_test_case_archive
from app.services.test_sets import (
    activate_test_set,
    add_test_case,
    create_test_set,
    deactivate_test_set,
    delete_test_set,
    list_test_sets,
    test_set_error,
    validate_and_mark,
    validate_test_set,
)

router = APIRouter(prefix="/admin/problems", tags=["题库管理"])


async def audit_admin_action(
    db: AsyncSession,
    admin: User,
    action: str,
    target_type: str,
    target_id: int | UUID,
    metadata: Optional[dict] = None,
) -> None:
    record_audit(
        db,
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=admin.id,
        metadata=metadata,
    )
    await db.commit()


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


@router.get("", response_model=AdminProblemPage)
async def list_admin_problems(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
    q: Annotated[Optional[str], Query(max_length=200)] = None,
    difficulty: Optional[ProblemDifficulty] = None,
    visibility: Annotated[Optional[ProblemVisibility], Query(alias="status")] = None,
    tag: Annotated[Optional[str], Query(max_length=50)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: AdminProblemSort = AdminProblemSort.UPDATED_DESC,
) -> AdminProblemPage:
    filters = []
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(Problem.title.ilike(pattern), Problem.slug.ilike(pattern)))
    if difficulty is not None:
        filters.append(Problem.difficulty == difficulty)
    if visibility is not None:
        filters.append(Problem.visibility == visibility)
    if tag:
        filters.append(
            exists(
                select(literal(1))
                .select_from(ProblemTag)
                .join(Tag, Tag.id == ProblemTag.tag_id)
                .where(ProblemTag.problem_id == Problem.id, Tag.slug == tag)
            )
        )
    orders = {
        AdminProblemSort.CREATED_DESC: (Problem.created_at.desc(), Problem.id.desc()),
        AdminProblemSort.CREATED_ASC: (Problem.created_at.asc(), Problem.id.asc()),
        AdminProblemSort.UPDATED_DESC: (Problem.updated_at.desc(), Problem.id.desc()),
        AdminProblemSort.UPDATED_ASC: (Problem.updated_at.asc(), Problem.id.asc()),
    }
    total = int(await db.scalar(select(func.count(Problem.id)).where(*filters)) or 0)
    rows = (
        await db.scalars(
            select(Problem)
            .options(selectinload(Problem.tag_links).selectinload(ProblemTag.tag))
            .where(*filters)
            .order_by(*orders[sort])
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return AdminProblemPage(
        items=[to_admin_problem(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total else 0,
    )


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
    result = await save_problem(db, problem)
    await audit_admin_action(db, current_admin, "problem.create", "problem", result.id)
    return result


@router.patch("/{problem_id}", response_model=AdminProblem)
async def update_problem(
    problem_id: int,
    payload: ProblemUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(get_admin_user)],
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
        "data_constraints",
        "sample_input",
        "sample_output",
        "sample_explanation",
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
    result = await save_problem(db, problem)
    await audit_admin_action(db, current_admin, "problem.update", "problem", problem_id)
    return result


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
    current_admin: Annotated[User, Depends(get_admin_user)],
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
    result = await set_visibility(problem_id, ProblemVisibility.PUBLIC, db)
    await audit_admin_action(db, current_admin, "problem.publish", "problem", problem_id)
    return result


@router.post("/{problem_id}/offline", response_model=AdminProblem)
async def offline_problem(
    problem_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(get_admin_user)],
) -> AdminProblem:
    result = await set_visibility(problem_id, ProblemVisibility.PRIVATE, db)
    await audit_admin_action(db, current_admin, "problem.offline", "problem", problem_id)
    return result


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


@router.get("/{problem_id}/readiness", response_model=ProblemReadinessPublic)
async def get_problem_readiness(
    problem_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    object_store: Annotated[SourceObjectStore, Depends(get_source_object_store)],
    _: Annotated[User, Depends(get_admin_user)],
) -> ProblemReadinessPublic:
    from app.services.test_sets import to_test_set_public

    problem = await db.get(Problem, problem_id)
    if problem is None:
        raise admin_problem_not_found()
    active = await db.scalar(
        select(TestSet)
        .options(selectinload(TestSet.cases))
        .where(TestSet.problem_id == problem_id, TestSet.status == TestSetStatus.ACTIVE)
    )
    if active is None:
        from app.schemas.test_set import TestSetIssue

        return ProblemReadinessPublic(
            ready=False,
            issues=[TestSetIssue(code="NO_ACTIVE_TEST_SET", message="题目缺少活动测试集")],
        )
    issues = await validate_test_set(db, active, object_store)
    return ProblemReadinessPublic(
        ready=not issues,
        active_test_set=to_test_set_public(active),
        issues=issues,
    )


@router.get("/test-sets/{test_set_id}", response_model=TestSetAdminPublic)
async def get_admin_test_set(
    test_set_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> TestSetAdminPublic:
    from app.services.test_sets import get_test_set, to_test_set_public

    test_set = await get_test_set(db, test_set_id)
    if test_set is None:
        raise test_set_error(404, "TEST_SET_NOT_FOUND", "测试集不存在")
    return to_test_set_public(test_set)


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
    result = await create_test_set(db, problem_id, current_admin.id, payload)
    await audit_admin_action(db, current_admin, "test_set.create", "test_set", result.id)
    return result


@router.post(
    "/test-sets/{test_set_id}/cases/upload",
    response_model=TestCaseBatchUploadPublic,
)
async def upload_test_set_cases(
    test_set_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    object_store: Annotated[SourceObjectStore, Depends(get_source_object_store)],
    current_admin: Annotated[User, Depends(get_admin_user)],
    archive: Annotated[UploadFile, File(description="ZIP archive with manifest.json")],
) -> TestCaseBatchUploadPublic:
    if archive.content_type not in {"application/zip", "application/x-zip-compressed"}:
        raise test_set_error(415, "UNSUPPORTED_ARCHIVE", "仅支持 ZIP 测试数据包")
    content = await archive.read(settings.test_data_archive_max_bytes + 1)
    if len(content) > settings.test_data_archive_max_bytes:
        raise test_set_error(413, "TEST_DATA_ARCHIVE_TOO_LARGE", "测试数据包超过大小限制")
    result = await upload_test_case_archive(db, test_set_id, content, object_store)
    await audit_admin_action(
        db,
        current_admin,
        "test_set.upload_cases",
        "test_set",
        test_set_id,
        {"case_count": result.uploaded_count},
    )
    return result


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
    current_admin: Annotated[User, Depends(get_admin_user)],
) -> TestCaseAdminPublic:
    result = await add_test_case(db, test_set_id, payload, object_store)
    await audit_admin_action(db, current_admin, "test_set.add_case", "test_set", test_set_id)
    return result


@router.post(
    "/test-sets/{test_set_id}/validate",
    response_model=TestSetValidationPublic,
)
async def validate_admin_test_set(
    test_set_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    object_store: Annotated[SourceObjectStore, Depends(get_source_object_store)],
    current_admin: Annotated[User, Depends(get_admin_user)],
) -> TestSetValidationPublic:
    result = await validate_and_mark(db, test_set_id, object_store)
    await audit_admin_action(
        db,
        current_admin,
        "test_set.validate",
        "test_set",
        test_set_id,
        {"valid": not result.issues, "issue_count": len(result.issues)},
    )
    return result


@router.post(
    "/test-sets/{test_set_id}/activate",
    response_model=TestSetAdminPublic,
)
async def activate_admin_test_set(
    test_set_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    object_store: Annotated[SourceObjectStore, Depends(get_source_object_store)],
    current_admin: Annotated[User, Depends(get_admin_user)],
) -> TestSetAdminPublic:
    result = await activate_test_set(db, test_set_id, object_store)
    await audit_admin_action(db, current_admin, "test_set.activate", "test_set", test_set_id)
    return result


@router.post("/test-sets/{test_set_id}/deactivate", response_model=TestSetAdminPublic)
async def deactivate_admin_test_set(
    test_set_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(get_admin_user)],
) -> TestSetAdminPublic:
    result = await deactivate_test_set(db, test_set_id)
    await audit_admin_action(db, current_admin, "test_set.deactivate", "test_set", test_set_id)
    return result


@router.delete(
    "/test-sets/{test_set_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_admin_test_set(
    test_set_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(get_admin_user)],
) -> None:
    await delete_test_set(db, test_set_id)
    await audit_admin_action(db, current_admin, "test_set.delete", "test_set", test_set_id)


@router.get("/{problem_id}", response_model=AdminProblem)
async def get_admin_problem(
    problem_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> AdminProblem:
    problem = await get_problem_with_tags(db, problem_id, public_only=False)
    if problem is None:
        raise admin_problem_not_found()
    return to_admin_problem(problem)
