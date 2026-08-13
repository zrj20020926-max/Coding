from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.problem import (
    CheckerType,
    Language,
    Problem,
    TestCase,
    TestGroup,
    TestSet,
    TestSetStatus,
)
from app.models.submission import Submission
from app.schemas.test_set import (
    TestCaseAdminPublic,
    TestCaseCreate,
    TestGroupAdminPublic,
    TestGroupCreate,
    TestSetAdminPublic,
    TestSetCreate,
    TestSetIssue,
    TestSetValidationPublic,
)
from app.services.object_storage import SourceObjectStore


def test_set_error(
    http_status: int, code: str, message: str, issues: list[TestSetIssue] | None = None
) -> HTTPException:
    detail: dict = {"code": code, "message": message}
    if issues is not None:
        detail["issues"] = [issue.model_dump(exclude_none=True) for issue in issues]
    return HTTPException(status_code=http_status, detail=detail)


def to_test_set_public(
    test_set: TestSet, submission_reference_count: int = 0
) -> TestSetAdminPublic:
    return TestSetAdminPublic(
        id=test_set.id,
        problem_id=test_set.problem_id,
        version=test_set.version,
        status=test_set.status,
        checker_type=test_set.checker_type,
        absolute_tolerance=test_set.absolute_tolerance,
        relative_tolerance=test_set.relative_tolerance,
        case_count=test_set.case_count,
        total_score=test_set.total_score,
        created_by=test_set.created_by,
        created_at=test_set.created_at,
        activated_at=test_set.activated_at,
        submission_reference_count=submission_reference_count,
        cases=[
            TestCaseAdminPublic(
                id=case.id,
                sequence=case.sequence,
                score=case.score,
                input_size_bytes=case.input_size_bytes,
                output_size_bytes=case.output_size_bytes,
                group_id=case.group_id,
            )
            for case in test_set.cases
        ],
        groups=[
            TestGroupAdminPublic(
                id=group.id,
                name=group.name,
                sequence=group.sequence,
                score=group.score,
                short_circuit=group.short_circuit,
                dependency_group_id=group.dependency_group_id,
                case_count=len(group.cases),
            )
            for group in test_set.groups
        ],
    )


async def get_test_set(db: AsyncSession, test_set_id: UUID, lock: bool = False) -> TestSet | None:
    statement = (
        select(TestSet)
        .options(selectinload(TestSet.cases), selectinload(TestSet.groups))
        .where(TestSet.id == test_set_id)
    )
    if lock:
        statement = statement.with_for_update(of=TestSet)
    return await db.scalar(statement)


async def list_test_sets(db: AsyncSession, problem_id: int) -> list[TestSetAdminPublic]:
    if await db.get(Problem, problem_id) is None:
        raise test_set_error(status.HTTP_404_NOT_FOUND, "PROBLEM_NOT_FOUND", "题目不存在")
    rows = (
        await db.scalars(
            select(TestSet)
            .options(selectinload(TestSet.cases), selectinload(TestSet.groups))
            .where(TestSet.problem_id == problem_id)
            .order_by(TestSet.version.desc())
        )
    ).all()
    counts = dict(
        (
            await db.execute(
                select(Submission.test_set_id, func.count(Submission.id))
                .where(Submission.test_set_id.in_([row.id for row in rows]))
                .group_by(Submission.test_set_id)
            )
        ).all()
    ) if rows else {}
    return [to_test_set_public(row, int(counts.get(row.id, 0))) for row in rows]


async def create_test_set(
    db: AsyncSession, problem_id: int, creator_id: UUID, payload: TestSetCreate
) -> TestSetAdminPublic:
    problem = await db.scalar(select(Problem).where(Problem.id == problem_id).with_for_update())
    if problem is None:
        raise test_set_error(status.HTTP_404_NOT_FOUND, "PROBLEM_NOT_FOUND", "题目不存在")
    next_version = (
        await db.scalar(
            select(func.coalesce(func.max(TestSet.version), 0) + 1).where(
                TestSet.problem_id == problem_id
            )
        )
    )
    test_set = TestSet(
        problem_id=problem_id,
        version=next_version,
        checker_type=payload.checker_type,
        absolute_tolerance=payload.absolute_tolerance,
        relative_tolerance=payload.relative_tolerance,
        created_by=creator_id,
    )
    db.add(test_set)
    await db.commit()
    loaded = await get_test_set(db, test_set.id)
    assert loaded is not None
    return to_test_set_public(loaded)


async def add_test_case(
    db: AsyncSession,
    test_set_id: UUID,
    payload: TestCaseCreate,
    object_store: SourceObjectStore,
) -> TestCaseAdminPublic:
    test_set = await get_test_set(db, test_set_id, lock=True)
    if test_set is None:
        raise test_set_error(status.HTTP_404_NOT_FOUND, "TEST_SET_NOT_FOUND", "测试集不存在")
    referenced = await db.scalar(
        select(func.count(Submission.id)).where(Submission.test_set_id == test_set_id)
    )
    if referenced or test_set.status not in {TestSetStatus.DRAFT, TestSetStatus.INVALID}:
        raise test_set_error(
            status.HTTP_409_CONFLICT,
            "TEST_SET_IMMUTABLE",
            "已引用或非草稿测试集不可修改",
        )
    try:
        input_data = await object_store.get_test_data(payload.input_object_key)
        output_data = await object_store.get_test_data(payload.output_object_key)
    except Exception as exc:
        raise test_set_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "TEST_DATA_UNAVAILABLE",
            "测试数据对象不存在或超出大小限制",
        ) from exc
    actual_checksum = hashlib.sha256(input_data + b"\0" + output_data).hexdigest()
    if actual_checksum != payload.checksum:
        raise test_set_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "TEST_DATA_CHECKSUM_MISMATCH",
            "测试数据校验失败",
        )
    group = None
    if payload.group_id is not None:
        group = next((item for item in test_set.groups if item.id == payload.group_id), None)
        if group is None:
            raise test_set_error(422, "TEST_GROUP_INVALID", "测试组不属于当前测试集")
    else:
        if payload.score <= 0:
            raise test_set_error(422, "TEST_GROUP_SCORE_REQUIRED", "自动测试组需要正分值")
        group = TestGroup(
            test_set_id=test_set_id,
            name=f"case-{payload.sequence}",
            sequence=payload.sequence,
            score=payload.score,
            short_circuit=True,
        )
    case = TestCase(
        test_set_id=test_set_id,
        group=group,
        sequence=payload.sequence,
        score=payload.score,
        input_object_key=payload.input_object_key,
        output_object_key=payload.output_object_key,
        checksum=payload.checksum,
        input_size_bytes=len(input_data),
        output_size_bytes=len(output_data),
    )
    db.add(case)
    test_set.case_count = len(test_set.cases) + 1
    test_set.total_score = sum(
        (existing.score for existing in test_set.groups), Decimal("0")
    ) + (group.score if group not in test_set.groups else Decimal("0"))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise test_set_error(
            status.HTTP_409_CONFLICT,
            "TEST_CASE_SEQUENCE_CONFLICT",
            "同一测试集中的用例序号必须唯一",
        ) from None
    return TestCaseAdminPublic(
        id=case.id,
        sequence=case.sequence,
        score=case.score,
        input_size_bytes=case.input_size_bytes,
        output_size_bytes=case.output_size_bytes,
        group_id=case.group_id,
    )


async def add_test_group(
    db: AsyncSession, test_set_id: UUID, payload: TestGroupCreate
) -> TestGroupAdminPublic:
    test_set = await get_test_set(db, test_set_id, lock=True)
    if test_set is None:
        raise test_set_error(404, "TEST_SET_NOT_FOUND", "测试集不存在")
    referenced = await db.scalar(
        select(func.count(Submission.id)).where(Submission.test_set_id == test_set_id)
    )
    if referenced or test_set.status not in {TestSetStatus.DRAFT, TestSetStatus.INVALID}:
        raise test_set_error(409, "TEST_SET_IMMUTABLE", "已引用或非草稿测试集不可修改")
    if payload.dependency_group_id is not None:
        dependency = next(
            (item for item in test_set.groups if item.id == payload.dependency_group_id), None
        )
        if dependency is None or dependency.sequence >= payload.sequence:
            raise test_set_error(
                422, "TEST_GROUP_DEPENDENCY_INVALID", "测试组只能依赖当前测试集中的前序组"
            )
    group = TestGroup(
        test_set_id=test_set_id,
        name=payload.name,
        sequence=payload.sequence,
        score=payload.score,
        short_circuit=payload.short_circuit,
        dependency_group_id=payload.dependency_group_id,
    )
    db.add(group)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise test_set_error(409, "TEST_GROUP_SEQUENCE_CONFLICT", "测试组序号必须唯一") from None
    return TestGroupAdminPublic(
        id=group.id,
        name=group.name,
        sequence=group.sequence,
        score=group.score,
        short_circuit=group.short_circuit,
        dependency_group_id=group.dependency_group_id,
        case_count=0,
    )


def _checker_issues(test_set: TestSet) -> list[TestSetIssue]:
    if test_set.checker_type is CheckerType.FLOAT:
        absolute = test_set.absolute_tolerance
        relative = test_set.relative_tolerance
        if absolute is None or relative is None or absolute < 0 or relative < 0:
            return [
                TestSetIssue(
                    code="CHECKER_CONFIG_INVALID", message="浮点 checker 容差配置无效"
                )
            ]
        if absolute == 0 and relative == 0:
            return [
                TestSetIssue(
                    code="CHECKER_CONFIG_INVALID",
                    message="浮点 checker 至少需要一个正容差",
                )
            ]
    elif test_set.absolute_tolerance is not None or test_set.relative_tolerance is not None:
        return [TestSetIssue(code="CHECKER_CONFIG_INVALID", message="当前 checker 不接受容差配置")]
    return []


async def validate_test_set(
    db: AsyncSession, test_set: TestSet, object_store: SourceObjectStore
) -> list[TestSetIssue]:
    """Validate checker, group graph, score total and every hidden object."""
    issues = _checker_issues(test_set)
    if not test_set.cases:
        issues.append(TestSetIssue(code="NO_HIDDEN_CASES", message="测试集至少需要一个隐藏用例"))
    sequences = [case.sequence for case in test_set.cases]
    if len(sequences) != len(set(sequences)):
        issues.append(TestSetIssue(code="DUPLICATE_SEQUENCE", message="测试用例序号重复"))
    if not test_set.groups:
        issues.append(TestSetIssue(code="NO_TEST_GROUPS", message="测试集至少需要一个测试组"))
    if sum((group.score for group in test_set.groups), Decimal("0")) != Decimal("100"):
        issues.append(TestSetIssue(code="INVALID_TOTAL_SCORE", message="测试组总分必须等于 100"))

    group_ids = {group.id for group in test_set.groups}
    group_sequences = {group.id: group.sequence for group in test_set.groups}
    for group in test_set.groups:
        if not group.cases:
            issues.append(TestSetIssue(code="EMPTY_TEST_GROUP", message="测试组不能为空"))
        if group.dependency_group_id is not None and (
            group.dependency_group_id not in group_ids
            or group_sequences[group.dependency_group_id] >= group.sequence
        ):
            issues.append(
                TestSetIssue(code="INVALID_GROUP_DEPENDENCY", message="测试组依赖无效")
            )

    for case in test_set.cases:
        if case.group_id not in group_ids:
            issues.append(
                TestSetIssue(
                    code="INVALID_CASE_GROUP",
                    message="测试用例未关联有效测试组",
                    sequence=case.sequence,
                )
            )
        if case.score < 0 or case.score > 100:
            issues.append(
                TestSetIssue(
                    code="INVALID_CASE_SCORE",
                    message="测试用例分值必须在 0 到 100 之间",
                    sequence=case.sequence,
                )
            )
        try:
            input_data = await object_store.get_test_data(case.input_object_key)
            output_data = await object_store.get_test_data(case.output_object_key)
        except Exception:
            issues.append(
                TestSetIssue(
                    code="TEST_DATA_UNAVAILABLE",
                    message="测试数据对象不存在或超出大小限制",
                    sequence=case.sequence,
                )
            )
            continue
        if (
            len(input_data) > settings.test_data_object_max_bytes
            or len(output_data) > settings.test_data_object_max_bytes
        ):
            issues.append(
                TestSetIssue(
                    code="TEST_DATA_TOO_LARGE",
                    message="测试数据超出大小限制",
                    sequence=case.sequence,
                )
            )
            continue
        checksum = hashlib.sha256(input_data + b"\0" + output_data).hexdigest()
        if checksum != case.checksum:
            issues.append(
                TestSetIssue(
                    code="CHECKSUM_MISMATCH",
                    message="测试数据校验失败",
                    sequence=case.sequence,
                )
            )
        if (
            len(input_data) != case.input_size_bytes
            or len(output_data) != case.output_size_bytes
        ):
            issues.append(
                TestSetIssue(
                    code="TEST_DATA_SIZE_MISMATCH",
                    message="测试数据大小与已验证元数据不一致",
                    sequence=case.sequence,
                )
            )

    language_slugs = set(
        (
            await db.scalars(
                select(Language.slug).where(
                    Language.enabled.is_(True), Language.slug.in_(["python", "cpp"])
                )
            )
        ).all()
    )
    configured = set(settings.judge_supported_language_list)
    for language in ("python", "cpp"):
        if language not in language_slugs or language not in configured:
            issues.append(
                TestSetIssue(
                    code="LANGUAGE_UNAVAILABLE", message=f"判题语言 {language} 未启用"
                )
            )
    return issues


async def validate_and_mark(
    db: AsyncSession, test_set_id: UUID, object_store: SourceObjectStore
) -> TestSetValidationPublic:
    test_set = await get_test_set(db, test_set_id, lock=True)
    if test_set is None:
        raise test_set_error(status.HTTP_404_NOT_FOUND, "TEST_SET_NOT_FOUND", "测试集不存在")
    if test_set.status in {TestSetStatus.ACTIVE, TestSetStatus.INACTIVE}:
        raise test_set_error(
            status.HTTP_409_CONFLICT,
            "TEST_SET_IMMUTABLE",
            "已激活测试集不可重新验证",
        )
    test_set.status = TestSetStatus.VALIDATING
    await db.flush()
    issues = await validate_test_set(db, test_set, object_store)
    test_set.status = TestSetStatus.INVALID if issues else TestSetStatus.READY
    await db.commit()
    loaded = await get_test_set(db, test_set_id)
    assert loaded is not None
    return TestSetValidationPublic(test_set=to_test_set_public(loaded), issues=issues)


async def activate_test_set(
    db: AsyncSession, test_set_id: UUID, object_store: SourceObjectStore
) -> TestSetAdminPublic:
    # Resolve ownership first, then use a consistent problem -> test-set lock order.
    # This serializes activation per problem without deadlocking two competing versions.
    owner_problem_id = await db.scalar(
        select(TestSet.problem_id).where(TestSet.id == test_set_id)
    )
    if owner_problem_id is None:
        raise test_set_error(status.HTTP_404_NOT_FOUND, "TEST_SET_NOT_FOUND", "测试集不存在")
    await db.scalar(
        select(Problem).where(Problem.id == owner_problem_id).with_for_update()
    )
    test_set = await get_test_set(db, test_set_id, lock=True)
    if test_set is None:
        raise test_set_error(status.HTTP_404_NOT_FOUND, "TEST_SET_NOT_FOUND", "测试集不存在")
    issues = await validate_test_set(db, test_set, object_store)
    if issues:
        if test_set.status not in {TestSetStatus.ACTIVE, TestSetStatus.INACTIVE}:
            test_set.status = TestSetStatus.INVALID
            await db.commit()
        raise test_set_error(
            status.HTTP_409_CONFLICT,
            "TEST_SET_NOT_READY",
            "测试集未通过完整性验证",
            issues,
        )
    if test_set.status not in {TestSetStatus.READY, TestSetStatus.ACTIVE}:
        raise test_set_error(
            status.HTTP_409_CONFLICT,
            "INVALID_TEST_SET_STATE",
            "只有 ready 测试集可以激活",
        )
    if test_set.status is TestSetStatus.ACTIVE:
        return to_test_set_public(test_set)
    current = await db.scalar(
        select(TestSet)
        .where(
            TestSet.problem_id == test_set.problem_id,
            TestSet.status == TestSetStatus.ACTIVE,
        )
        .with_for_update()
    )
    if current is not None:
        current.status = TestSetStatus.INACTIVE
    test_set.status = TestSetStatus.ACTIVE
    test_set.activated_at = datetime.now(timezone.utc)
    await db.commit()
    loaded = await get_test_set(db, test_set.id)
    assert loaded is not None
    return to_test_set_public(loaded)


async def delete_test_set(db: AsyncSession, test_set_id: UUID) -> None:
    test_set = await get_test_set(db, test_set_id, lock=True)
    if test_set is None:
        raise test_set_error(status.HTTP_404_NOT_FOUND, "TEST_SET_NOT_FOUND", "测试集不存在")
    referenced = await db.scalar(
        select(func.count(Submission.id)).where(Submission.test_set_id == test_set_id)
    )
    if referenced or test_set.status is not TestSetStatus.DRAFT:
        raise test_set_error(
            status.HTTP_409_CONFLICT,
            "TEST_SET_IMMUTABLE",
            "只能删除未引用的草稿测试集",
        )
    await db.delete(test_set)
    await db.commit()


async def deactivate_test_set(db: AsyncSession, test_set_id: UUID) -> TestSetAdminPublic:
    test_set = await get_test_set(db, test_set_id, lock=True)
    if test_set is None:
        raise test_set_error(status.HTTP_404_NOT_FOUND, "TEST_SET_NOT_FOUND", "测试集不存在")
    referenced = await db.scalar(
        select(func.count(Submission.id)).where(Submission.test_set_id == test_set_id)
    )
    if referenced or test_set.status is not TestSetStatus.DRAFT:
        raise test_set_error(
            status.HTTP_409_CONFLICT,
            "TEST_SET_CANNOT_DEACTIVATE",
            "只能停用未被提交引用的草稿测试集",
        )
    test_set.status = TestSetStatus.INACTIVE
    await db.commit()
    loaded = await get_test_set(db, test_set_id)
    assert loaded is not None
    return to_test_set_public(loaded)
