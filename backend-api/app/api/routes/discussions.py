from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.content import (
    CommentCreate,
    CommentPublic,
    CommentUpdate,
    DiscussionCreate,
    DiscussionDetail,
    DiscussionPage,
    DiscussionPublic,
    DiscussionUpdate,
    ReportCreate,
    ReportState,
)
from app.services.discussions import (
    create_comment,
    create_discussion,
    create_report,
    delete_comment,
    delete_discussion,
    edit_comment,
    edit_discussion,
    get_discussion_detail,
    list_discussions,
)

router = APIRouter(tags=["讨论区"])


@router.get("/problems/{problem_id}/discussions", response_model=DiscussionPage)
async def get_problem_discussions(
    problem_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DiscussionPage:
    return await list_discussions(db, problem_id, current_user, page, page_size)


@router.post(
    "/problems/{problem_id}/discussions",
    response_model=DiscussionPublic,
    status_code=status.HTTP_201_CREATED,
)
async def add_problem_discussion(
    problem_id: int,
    payload: DiscussionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DiscussionPublic:
    return await create_discussion(
        db, problem_id, current_user, payload.title, payload.content
    )


@router.get("/discussions/{discussion_id}", response_model=DiscussionDetail)
async def get_discussion(
    discussion_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Optional[User], Depends(get_optional_current_user)],
    comments_page: Annotated[int, Query(ge=1)] = 1,
    comments_page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> DiscussionDetail:
    return await get_discussion_detail(
        db,
        discussion_id,
        current_user,
        comments_page,
        comments_page_size,
    )


@router.patch("/discussions/{discussion_id}", response_model=DiscussionPublic)
async def update_discussion(
    discussion_id: int,
    payload: DiscussionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DiscussionPublic:
    return await edit_discussion(
        db,
        discussion_id,
        current_user,
        payload.title,
        payload.content,
    )


@router.delete(
    "/discussions/{discussion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_discussion(
    discussion_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    await delete_discussion(db, discussion_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/discussions/{discussion_id}/comments",
    response_model=CommentPublic,
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    discussion_id: int,
    payload: CommentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CommentPublic:
    return await create_comment(
        db,
        discussion_id,
        current_user,
        payload.content,
        payload.parent_id,
    )


@router.patch("/comments/{comment_id}", response_model=CommentPublic)
async def update_comment(
    comment_id: int,
    payload: CommentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CommentPublic:
    return await edit_comment(db, comment_id, current_user, payload.content)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_comment(
    comment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    await delete_comment(db, comment_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/discussions/{discussion_id}/reports", response_model=ReportState)
async def report_discussion(
    discussion_id: int,
    payload: ReportCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReportState:
    return await create_report(
        db,
        current_user.id,
        payload.reason,
        discussion_id=discussion_id,
    )


@router.post("/comments/{comment_id}/reports", response_model=ReportState)
async def report_comment(
    comment_id: int,
    payload: ReportCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ReportState:
    return await create_report(
        db,
        current_user.id,
        payload.reason,
        comment_id=comment_id,
    )
