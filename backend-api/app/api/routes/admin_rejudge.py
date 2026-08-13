from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.rejudge import (
    BatchRejudgeCreate,
    RejudgeTaskPage,
    RejudgeTaskPublic,
    SingleRejudgeCreate,
)
from app.services.rejudge import (
    create_batch_rejudge,
    create_single_rejudge,
    get_rejudge_task,
    list_rejudge_tasks,
)

router = APIRouter(prefix="/admin/rejudge", tags=["重判管理"])


@router.get("", response_model=RejudgeTaskPage)
async def get_rejudge_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RejudgeTaskPage:
    return await list_rejudge_tasks(db, page, page_size)


@router.get("/{task_id}", response_model=RejudgeTaskPublic)
async def get_rejudge_task_detail(
    task_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
) -> RejudgeTaskPublic:
    return await get_rejudge_task(db, task_id)


@router.post("/submissions", response_model=RejudgeTaskPublic, status_code=status.HTTP_202_ACCEPTED)
async def rejudge_submission(
    payload: SingleRejudgeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> RejudgeTaskPublic:
    return await create_single_rejudge(db, admin, payload.submission_id)


@router.post("/batch", response_model=RejudgeTaskPublic, status_code=status.HTTP_202_ACCEPTED)
async def rejudge_problem_batch(
    payload: BatchRejudgeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> RejudgeTaskPublic:
    return await create_batch_rejudge(db, admin, payload.problem_id, payload.test_set_id)
