from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.content import (
    CommentPublic,
    ContentReportPage,
    ContentReportPublic,
    DiscussionAdminUpdate,
    DiscussionPublic,
    ModerationUpdate,
    ReportAdminUpdate,
)
from app.services.discussions import (
    handle_report,
    list_reports,
    moderate_comment,
    moderate_discussion,
    set_discussion_controls,
)

router = APIRouter(prefix="/admin", tags=["讨论区管理"])


@router.patch(
    "/discussions/{discussion_id}/moderation",
    response_model=DiscussionPublic,
)
async def review_discussion(
    discussion_id: int,
    payload: ModerationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> DiscussionPublic:
    return await moderate_discussion(
        db, discussion_id, admin, payload.review_status, payload.reason
    )


@router.patch("/comments/{comment_id}/moderation", response_model=CommentPublic)
async def review_comment(
    comment_id: int,
    payload: ModerationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> CommentPublic:
    return await moderate_comment(
        db, comment_id, admin, payload.review_status, payload.reason
    )


@router.patch("/discussions/{discussion_id}/controls", response_model=DiscussionPublic)
async def control_discussion(
    discussion_id: int,
    payload: DiscussionAdminUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> DiscussionPublic:
    return await set_discussion_controls(
        db,
        discussion_id,
        admin,
        payload.is_pinned,
        payload.is_locked,
    )


@router.get("/content-reports", response_model=ContentReportPage)
async def get_content_reports(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_admin_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    report_status: Optional[Literal["pending", "resolved", "dismissed"]] = None,
) -> ContentReportPage:
    return await list_reports(db, page, page_size, report_status)


@router.patch("/content-reports/{report_id}", response_model=ContentReportPublic)
async def update_content_report(
    report_id: int,
    payload: ReportAdminUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(get_admin_user)],
) -> ContentReportPublic:
    return await handle_report(
        db,
        report_id,
        admin,
        payload.status,
        payload.reason,
    )
