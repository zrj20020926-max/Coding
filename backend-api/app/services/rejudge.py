from __future__ import annotations

from math import ceil
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.problem import Problem, TestSet, TestSetStatus
from app.models.submission import (
    Outbox,
    RejudgeTask,
    RejudgeTaskItem,
    Submission,
    SubmissionMode,
    SubmissionStatus,
)
from app.models.user import User
from app.schemas.rejudge import RejudgeTaskPage, RejudgeTaskPublic
from app.services.audit import record_audit
from app.services.submissions import TERMINAL_STATUSES


def rejudge_error(http_status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "message": message})


async def _load_target_test_set(
    db: AsyncSession, problem_id: int, test_set_id: UUID
) -> TestSet:
    test_set = await db.scalar(
        select(TestSet).where(
            TestSet.id == test_set_id,
            TestSet.problem_id == problem_id,
            TestSet.status.in_([TestSetStatus.ACTIVE, TestSetStatus.INACTIVE]),
        )
    )
    if test_set is None:
        raise rejudge_error(
            status.HTTP_409_CONFLICT,
            "TEST_SET_NOT_REJUDGEABLE",
            "只能使用已激活且不可变的测试集发起重判",
        )
    return test_set


def _clone_submission(original: Submission, test_set: TestSet, problem: Problem) -> Submission:
    return Submission(
        id=uuid4(),
        user_id=original.user_id,
        problem_id=original.problem_id,
        language_id=original.language_id,
        status=SubmissionStatus.PENDING,
        mode=SubmissionMode.JUDGE,
        test_set_id=test_set.id,
        problem_version=problem.version,
        time_limit_ms_snapshot=problem.time_limit_ms,
        memory_limit_mb_snapshot=problem.memory_limit_mb,
        source_code=None,
        source_object_key=original.source_object_key,
        source_checksum=original.source_checksum,
        is_rejudge=True,
        original_submission_id=original.id,
    )


async def _create_task(
    db: AsyncSession,
    admin: User,
    originals: list[Submission],
    test_set: TestSet,
    problem: Problem,
    mode: str,
) -> RejudgeTask:
    task = RejudgeTask(
        id=uuid4(),
        requested_by=admin.id,
        mode=mode,
        problem_id=problem.id,
        test_set_id=test_set.id,
        total_count=len(originals),
    )
    db.add(task)
    for original in originals:
        cloned = _clone_submission(original, test_set, problem)
        event_id = uuid4()
        db.add_all(
            [
                cloned,
                RejudgeTaskItem(
                    task_id=task.id,
                    original_submission_id=original.id,
                    rejudge_submission_id=cloned.id,
                ),
                Outbox(
                    id=event_id,
                    aggregate_type="submission",
                    aggregate_id=cloned.id,
                    event_type="submission.created",
                    payload={"event_id": str(event_id), "submission_id": str(cloned.id)},
                ),
            ]
        )
    record_audit(
        db,
        action=f"rejudge.{mode}.create",
        target_type="rejudge_task",
        target_id=task.id,
        actor_user_id=admin.id,
        metadata={"problem_id": problem.id, "submission_count": len(originals)},
    )
    await db.commit()
    return task


async def create_single_rejudge(
    db: AsyncSession, admin: User, submission_id: UUID
) -> RejudgeTaskPublic:
    original = await db.get(Submission, submission_id)
    if (
        original is None
        or original.mode is not SubmissionMode.JUDGE
        or original.status not in TERMINAL_STATUSES
        or original.test_set_id is None
        or not original.source_object_key
    ):
        raise rejudge_error(
            status.HTTP_409_CONFLICT,
            "SUBMISSION_NOT_REJUDGEABLE",
            "仅支持重判已结束且源码可用的正式提交",
        )
    problem = await db.get(Problem, original.problem_id)
    assert problem is not None
    test_set = await _load_target_test_set(db, problem.id, original.test_set_id)
    task = await _create_task(db, admin, [original], test_set, problem, "single")
    return await get_rejudge_task(db, task.id)


async def create_batch_rejudge(
    db: AsyncSession, admin: User, problem_id: int, test_set_id: UUID
) -> RejudgeTaskPublic:
    problem = await db.get(Problem, problem_id)
    if problem is None:
        raise rejudge_error(status.HTTP_404_NOT_FOUND, "PROBLEM_NOT_FOUND", "题目不存在")
    test_set = await _load_target_test_set(db, problem_id, test_set_id)
    originals = list(
        (
            await db.scalars(
                select(Submission)
                .where(
                    Submission.problem_id == problem_id,
                    Submission.mode == SubmissionMode.JUDGE,
                    Submission.is_rejudge.is_(False),
                    Submission.status.in_(TERMINAL_STATUSES),
                    Submission.source_object_key.is_not(None),
                )
                .order_by(Submission.created_at.asc(), Submission.id.asc())
                .limit(settings.rejudge_batch_max_submissions + 1)
            )
        ).all()
    )
    if not originals:
        raise rejudge_error(
            status.HTTP_409_CONFLICT, "NO_REJUDGE_CANDIDATES", "没有可重判的正式提交"
        )
    if len(originals) > settings.rejudge_batch_max_submissions:
        raise rejudge_error(
            status.HTTP_409_CONFLICT,
            "REJUDGE_BATCH_TOO_LARGE",
            f"批量重判最多支持 {settings.rejudge_batch_max_submissions} 条提交",
        )
    task = await _create_task(db, admin, originals, test_set, problem, "batch")
    return await get_rejudge_task(db, task.id)


def _status_from_counts(
    total: int, queued: int, running: int, success: int, failed: int
) -> str:
    if queued == total:
        return "queued"
    if queued or running:
        return "running"
    if success + failed == total:
        return "completed_with_errors" if failed else "completed"
    return "running"


async def _task_rows(db: AsyncSession, filters: list, offset: int, limit: int):
    failure_statuses = [SubmissionStatus.SYSTEM_ERROR]
    success_statuses = list(TERMINAL_STATUSES - {SubmissionStatus.SYSTEM_ERROR})
    return (
        await db.execute(
            select(
                RejudgeTask,
                func.sum(case((Submission.status == SubmissionStatus.PENDING, 1), else_=0)),
                func.sum(
                    case(
                        (
                            Submission.status.in_(
                                [SubmissionStatus.COMPILING, SubmissionStatus.RUNNING]
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                func.sum(case((Submission.status.in_(success_statuses), 1), else_=0)),
                func.sum(case((Submission.status.in_(failure_statuses), 1), else_=0)),
            )
            .join(RejudgeTaskItem, RejudgeTaskItem.task_id == RejudgeTask.id)
            .join(Submission, Submission.id == RejudgeTaskItem.rejudge_submission_id)
            .where(*filters)
            .group_by(RejudgeTask.id)
            .order_by(RejudgeTask.created_at.desc(), RejudgeTask.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()


def _to_public(row) -> RejudgeTaskPublic:
    task, queued, running, success, failed = row
    values = [int(value or 0) for value in (queued, running, success, failed)]
    return RejudgeTaskPublic(
        id=task.id,
        mode=task.mode,
        problem_id=task.problem_id,
        test_set_id=task.test_set_id,
        status=_status_from_counts(task.total_count, *values),
        total_count=task.total_count,
        queued_count=values[0],
        running_count=values[1],
        success_count=values[2],
        failed_count=values[3],
        created_at=task.created_at,
    )


async def get_rejudge_task(db: AsyncSession, task_id: UUID) -> RejudgeTaskPublic:
    rows = await _task_rows(db, [RejudgeTask.id == task_id], 0, 1)
    if not rows:
        raise rejudge_error(404, "REJUDGE_TASK_NOT_FOUND", "重判任务不存在")
    return _to_public(rows[0])


async def list_rejudge_tasks(
    db: AsyncSession, page: int, page_size: int
) -> RejudgeTaskPage:
    total = int(await db.scalar(select(func.count(RejudgeTask.id))) or 0)
    rows = await _task_rows(db, [], (page - 1) * page_size, page_size)
    return RejudgeTaskPage(
        items=[_to_public(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total else 0,
    )
