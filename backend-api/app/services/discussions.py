from __future__ import annotations

import math
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.content import (
    ContentModerationAction,
    ContentReport,
    ContentReviewStatus,
    Discussion,
    DiscussionComment,
)
from app.models.problem import Problem, ProblemVisibility
from app.models.user import User
from app.schemas.content import (
    CommentPage,
    CommentPublic,
    ContentAuthor,
    ContentReportPage,
    ContentReportPublic,
    DiscussionDetail,
    DiscussionPage,
    DiscussionPublic,
    ReportState,
)
from app.services.audit import record_audit
from app.services.collections import content_error


def review_content(*values: str) -> ContentReviewStatus:
    normalized = "\n".join(values).casefold()
    if any(word in normalized for word in settings.content_sensitive_word_list):
        return ContentReviewStatus.PENDING
    return ContentReviewStatus.APPROVED


def to_author(user: User | None) -> ContentAuthor | None:
    if user is None:
        return None
    return ContentAuthor(
        id=str(user.id),
        nickname=user.nickname,
        avatar_url=user.avatar_url,
    )


def to_discussion(
    discussion: Discussion, current_user: User | None
) -> DiscussionPublic:
    return DiscussionPublic(
        id=discussion.id,
        problem_id=discussion.problem_id,
        author=to_author(discussion.author) if discussion.user_id is not None else None,
        title=discussion.title,
        content=discussion.content,
        is_pinned=discussion.is_pinned,
        is_locked=discussion.is_locked,
        comment_count=discussion.comment_count,
        review_status=discussion.review_status,
        created_at=discussion.created_at,
        updated_at=discussion.updated_at,
        can_edit=bool(
            current_user
            and (current_user.is_admin or discussion.user_id == current_user.id)
            and discussion.deleted_at is None
        ),
    )


def to_comment(
    comment: DiscussionComment,
    current_user: User | None,
    *,
    discussion_locked: bool = False,
) -> CommentPublic:
    deleted = comment.deleted_at is not None
    return CommentPublic(
        id=comment.id,
        discussion_id=comment.discussion_id,
        parent_id=comment.parent_id,
        depth=comment.depth,
        author=to_author(comment.author) if comment.user_id is not None else None,
        content="[该评论已删除]" if deleted else comment.content,
        deleted=deleted,
        review_status=comment.review_status,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        can_edit=bool(
            current_user
            and not deleted
            and (current_user.is_admin or comment.user_id == current_user.id)
            and (current_user.is_admin or not discussion_locked)
        ),
    )


async def ensure_public_problem(db: AsyncSession, problem_id: int) -> Problem:
    problem = await db.scalar(
        select(Problem).where(
            Problem.id == problem_id,
            Problem.visibility == ProblemVisibility.PUBLIC,
        )
    )
    if problem is None:
        raise content_error(404, "PROBLEM_NOT_FOUND", "公开题目不存在")
    return problem


def _discussion_visibility(current_user: User | None):
    public = and_(
        Discussion.deleted_at.is_(None),
        Discussion.review_status == ContentReviewStatus.APPROVED,
    )
    if current_user is None:
        return public
    if current_user.is_admin:
        return Discussion.deleted_at.is_(None)
    return and_(
        Discussion.deleted_at.is_(None),
        or_(public, Discussion.user_id == current_user.id),
    )


async def list_discussions(
    db: AsyncSession,
    problem_id: int,
    current_user: User | None,
    page: int,
    page_size: int,
) -> DiscussionPage:
    await ensure_public_problem(db, problem_id)
    filters = [
        Discussion.problem_id == problem_id,
        _discussion_visibility(current_user),
    ]
    total = int(await db.scalar(select(func.count(Discussion.id)).where(*filters)) or 0)
    discussions = (
        await db.scalars(
            select(Discussion)
            .where(*filters)
            .order_by(
                Discussion.is_pinned.desc(),
                Discussion.created_at.desc(),
                Discussion.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return DiscussionPage(
        items=[to_discussion(item, current_user) for item in discussions],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def create_discussion(
    db: AsyncSession,
    problem_id: int,
    user: User,
    title: str,
    content: str,
) -> DiscussionPublic:
    await ensure_public_problem(db, problem_id)
    discussion = Discussion(
        problem_id=problem_id,
        user_id=user.id,
        title=title,
        content=content,
        review_status=review_content(title, content),
    )
    db.add(discussion)
    await db.commit()
    discussion.author = user
    return to_discussion(discussion, user)


async def _load_visible_discussion(
    db: AsyncSession, discussion_id: int, current_user: User | None
) -> Discussion:
    discussion = await db.scalar(
        select(Discussion)
        .join(Problem, Problem.id == Discussion.problem_id)
        .where(
            Discussion.id == discussion_id,
            Problem.visibility == ProblemVisibility.PUBLIC,
            _discussion_visibility(current_user),
        )
    )
    if discussion is None:
        raise content_error(404, "DISCUSSION_NOT_FOUND", "讨论不存在")
    return discussion


def _comment_visibility(current_user: User | None):
    public = DiscussionComment.review_status == ContentReviewStatus.APPROVED
    if current_user is None:
        return public
    if current_user.is_admin:
        return True
    return or_(public, DiscussionComment.user_id == current_user.id)


async def get_discussion_detail(
    db: AsyncSession,
    discussion_id: int,
    current_user: User | None,
    page: int,
    page_size: int,
) -> DiscussionDetail:
    discussion = await _load_visible_discussion(db, discussion_id, current_user)
    filters = [
        DiscussionComment.discussion_id == discussion_id,
        _comment_visibility(current_user),
    ]
    total = int(
        await db.scalar(select(func.count(DiscussionComment.id)).where(*filters)) or 0
    )
    comments = (
        await db.scalars(
            select(DiscussionComment)
            .where(*filters)
            .order_by(DiscussionComment.created_at.asc(), DiscussionComment.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return DiscussionDetail(
        discussion=to_discussion(discussion, current_user),
        comments=CommentPage(
            items=[
                to_comment(
                    item,
                    current_user,
                    discussion_locked=discussion.is_locked,
                )
                for item in comments
            ],
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        ),
    )


def require_owner_or_admin(user: User, owner_id: UUID | None) -> None:
    if not user.is_admin and owner_id != user.id:
        raise content_error(403, "FORBIDDEN", "无权修改该内容")


async def edit_discussion(
    db: AsyncSession,
    discussion_id: int,
    user: User,
    title: str | None,
    content: str | None,
) -> DiscussionPublic:
    discussion = await _load_visible_discussion(db, discussion_id, user)
    require_owner_or_admin(user, discussion.user_id)
    if discussion.is_locked and not user.is_admin:
        raise content_error(423, "DISCUSSION_LOCKED", "讨论已锁定")
    if title is not None:
        discussion.title = title
    if content is not None:
        discussion.content = content
    discussion.review_status = review_content(discussion.title, discussion.content)
    discussion.moderation_reason = None
    await db.commit()
    await db.refresh(discussion)
    return to_discussion(discussion, user)


async def delete_discussion(
    db: AsyncSession, discussion_id: int, user: User
) -> None:
    discussion = await _load_visible_discussion(db, discussion_id, user)
    require_owner_or_admin(user, discussion.user_id)
    discussion.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def create_comment(
    db: AsyncSession,
    discussion_id: int,
    user: User,
    content: str,
    parent_id: int | None,
) -> CommentPublic:
    discussion = await _load_visible_discussion(db, discussion_id, user)
    if discussion.review_status is not ContentReviewStatus.APPROVED:
        raise content_error(409, "DISCUSSION_PENDING", "讨论审核通过后才能评论")
    if discussion.is_locked:
        raise content_error(423, "DISCUSSION_LOCKED", "讨论已锁定")
    depth = 0
    if parent_id is not None:
        parent = await db.scalar(
            select(DiscussionComment).where(
                DiscussionComment.id == parent_id,
                DiscussionComment.discussion_id == discussion_id,
                DiscussionComment.deleted_at.is_(None),
                DiscussionComment.review_status == ContentReviewStatus.APPROVED,
            )
        )
        if parent is None:
            raise content_error(400, "INVALID_PARENT_COMMENT", "回复目标不存在")
        depth = parent.depth + 1
        if depth > settings.discussion_max_reply_depth:
            raise content_error(400, "REPLY_DEPTH_EXCEEDED", "评论回复层级过深")
    review_status = review_content(content)
    comment = DiscussionComment(
        discussion_id=discussion_id,
        user_id=user.id,
        parent_id=parent_id,
        depth=depth,
        content=content,
        review_status=review_status,
    )
    db.add(comment)
    await db.flush()
    if review_status is ContentReviewStatus.APPROVED:
        await db.execute(
            update(Discussion)
            .where(Discussion.id == discussion_id)
            .values(comment_count=Discussion.comment_count + 1)
        )
    await db.commit()
    comment.author = user
    return to_comment(comment, user)


async def _load_comment(
    db: AsyncSession,
    comment_id: int,
    *,
    for_update: bool = False,
) -> DiscussionComment:
    statement = select(DiscussionComment).where(DiscussionComment.id == comment_id)
    if for_update:
        statement = statement.with_for_update(of=DiscussionComment)
    comment = await db.scalar(statement)
    if comment is None:
        raise content_error(404, "COMMENT_NOT_FOUND", "评论不存在")
    return comment


async def _load_user_comment(
    db: AsyncSession,
    comment_id: int,
    user: User,
    *,
    for_update: bool = False,
) -> DiscussionComment:
    statement = (
        select(DiscussionComment)
        .join(Discussion, Discussion.id == DiscussionComment.discussion_id)
        .join(Problem, Problem.id == Discussion.problem_id)
        .where(DiscussionComment.id == comment_id)
    )
    if not user.is_admin:
        statement = statement.where(
            Problem.visibility == ProblemVisibility.PUBLIC,
            Discussion.deleted_at.is_(None),
        )
    if for_update:
        statement = statement.with_for_update(of=DiscussionComment)
    comment = await db.scalar(statement)
    if comment is None:
        raise content_error(404, "COMMENT_NOT_FOUND", "评论不存在")
    return comment


async def _load_reportable_comment(
    db: AsyncSession, comment_id: int
) -> DiscussionComment:
    comment = await db.scalar(
        select(DiscussionComment)
        .join(Discussion, Discussion.id == DiscussionComment.discussion_id)
        .join(Problem, Problem.id == Discussion.problem_id)
        .where(
            DiscussionComment.id == comment_id,
            DiscussionComment.deleted_at.is_(None),
            DiscussionComment.review_status == ContentReviewStatus.APPROVED,
            Discussion.deleted_at.is_(None),
            Discussion.review_status == ContentReviewStatus.APPROVED,
            Problem.visibility == ProblemVisibility.PUBLIC,
        )
    )
    if comment is None:
        raise content_error(404, "COMMENT_NOT_FOUND", "评论不存在")
    return comment


async def edit_comment(
    db: AsyncSession, comment_id: int, user: User, content: str
) -> CommentPublic:
    comment = await _load_user_comment(db, comment_id, user, for_update=True)
    require_owner_or_admin(user, comment.user_id)
    if comment.deleted_at is not None:
        raise content_error(409, "COMMENT_DELETED", "已删除评论不能编辑")
    discussion = await db.get(Discussion, comment.discussion_id)
    if discussion is None:
        raise content_error(404, "DISCUSSION_NOT_FOUND", "讨论不存在")
    if discussion.is_locked and not user.is_admin:
        raise content_error(423, "DISCUSSION_LOCKED", "讨论已锁定")
    was_approved = comment.review_status is ContentReviewStatus.APPROVED
    comment.content = content
    comment.review_status = review_content(content)
    comment.moderation_reason = None
    now_approved = comment.review_status is ContentReviewStatus.APPROVED
    if was_approved != now_approved:
        increment = 1 if now_approved else -1
        await db.execute(
            update(Discussion)
            .where(Discussion.id == comment.discussion_id)
            .values(
                comment_count=case(
                    (Discussion.comment_count + increment < 0, 0),
                    else_=Discussion.comment_count + increment,
                )
            )
        )
    await db.commit()
    await db.refresh(comment)
    return to_comment(comment, user)


async def delete_comment(db: AsyncSession, comment_id: int, user: User) -> None:
    comment = await _load_user_comment(db, comment_id, user, for_update=True)
    require_owner_or_admin(user, comment.user_id)
    if comment.deleted_at is not None:
        return
    was_approved = comment.review_status is ContentReviewStatus.APPROVED
    comment.deleted_at = datetime.now(timezone.utc)
    comment.content = ""
    if was_approved:
        await db.execute(
            update(Discussion)
            .where(Discussion.id == comment.discussion_id)
            .values(
                comment_count=case(
                    (Discussion.comment_count > 0, Discussion.comment_count - 1),
                    else_=0,
                )
            )
        )
    await db.commit()


async def create_report(
    db: AsyncSession,
    reporter_id: UUID,
    reason: str,
    *,
    discussion_id: int | None = None,
    comment_id: int | None = None,
) -> ReportState:
    if discussion_id is not None:
        await _load_visible_discussion(db, discussion_id, None)
    elif comment_id is not None:
        await _load_reportable_comment(db, comment_id)
    else:  # pragma: no cover - routes always supply one target
        raise content_error(400, "INVALID_REPORT", "举报目标无效")
    report = ContentReport(
        reporter_id=reporter_id,
        discussion_id=discussion_id,
        comment_id=comment_id,
        reason=reason,
    )
    db.add(report)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(
            select(ContentReport).where(
                ContentReport.reporter_id == reporter_id,
                ContentReport.discussion_id == discussion_id,
                ContentReport.comment_id == comment_id,
            )
        )
        if existing is None:  # pragma: no cover - unexpected constraint failure
            raise content_error(409, "REPORT_CONFLICT", "举报提交冲突") from None
        return ReportState(report_id=existing.id, created=False)
    target_type = Discussion if discussion_id is not None else DiscussionComment
    target_id = discussion_id if discussion_id is not None else comment_id
    await db.execute(
        update(target_type)
        .where(target_type.id == target_id)
        .values(report_count=target_type.report_count + 1)
    )
    await db.commit()
    return ReportState(report_id=report.id, created=True)


def add_moderation_action(
    db: AsyncSession,
    admin_id: UUID,
    target_type: str,
    target_id: int,
    action: str,
    reason: str | None,
) -> None:
    db.add(
        ContentModerationAction(
            admin_id=admin_id,
            target_type=target_type,
            target_id=target_id,
            action=action,
            reason=reason,
        )
    )


async def moderate_discussion(
    db: AsyncSession,
    discussion_id: int,
    admin: User,
    review_status: ContentReviewStatus,
    reason: str | None,
) -> DiscussionPublic:
    discussion = await db.get(Discussion, discussion_id)
    if discussion is None:
        raise content_error(404, "DISCUSSION_NOT_FOUND", "讨论不存在")
    discussion.review_status = review_status
    discussion.moderation_reason = reason
    discussion.moderated_by = admin.id
    discussion.moderated_at = datetime.now(timezone.utc)
    add_moderation_action(
        db, admin.id, "discussion", discussion_id, f"review:{review_status.value}", reason
    )
    record_audit(
        db,
        action="discussion.moderate",
        target_type="discussion",
        target_id=discussion_id,
        actor_user_id=admin.id,
        metadata={"review_status": review_status.value, "reason_provided": bool(reason)},
    )
    await db.commit()
    await db.refresh(discussion)
    return to_discussion(discussion, admin)


async def moderate_comment(
    db: AsyncSession,
    comment_id: int,
    admin: User,
    review_status: ContentReviewStatus,
    reason: str | None,
) -> CommentPublic:
    comment = await _load_comment(db, comment_id, for_update=True)
    was_visible = (
        comment.review_status is ContentReviewStatus.APPROVED
        and comment.deleted_at is None
    )
    comment.review_status = review_status
    comment.moderation_reason = reason
    comment.moderated_by = admin.id
    comment.moderated_at = datetime.now(timezone.utc)
    now_visible = review_status is ContentReviewStatus.APPROVED and comment.deleted_at is None
    if was_visible != now_visible:
        increment = 1 if now_visible else -1
        await db.execute(
            update(Discussion)
            .where(Discussion.id == comment.discussion_id)
            .values(
                comment_count=case(
                    (Discussion.comment_count + increment < 0, 0),
                    else_=Discussion.comment_count + increment,
                )
            )
        )
    add_moderation_action(
        db, admin.id, "comment", comment_id, f"review:{review_status.value}", reason
    )
    record_audit(
        db,
        action="comment.moderate",
        target_type="comment",
        target_id=comment_id,
        actor_user_id=admin.id,
        metadata={"review_status": review_status.value, "reason_provided": bool(reason)},
    )
    await db.commit()
    await db.refresh(comment)
    return to_comment(comment, admin)


async def set_discussion_controls(
    db: AsyncSession,
    discussion_id: int,
    admin: User,
    is_pinned: bool | None,
    is_locked: bool | None,
) -> DiscussionPublic:
    discussion = await db.get(Discussion, discussion_id)
    if discussion is None:
        raise content_error(404, "DISCUSSION_NOT_FOUND", "讨论不存在")
    actions: list[str] = []
    if is_pinned is not None:
        discussion.is_pinned = is_pinned
        actions.append("pin" if is_pinned else "unpin")
    if is_locked is not None:
        discussion.is_locked = is_locked
        actions.append("lock" if is_locked else "unlock")
    if not actions:
        raise content_error(400, "EMPTY_ADMIN_UPDATE", "未提供管理操作")
    add_moderation_action(
        db, admin.id, "discussion", discussion_id, "+".join(actions), None
    )
    record_audit(
        db,
        action="discussion.controls",
        target_type="discussion",
        target_id=discussion_id,
        actor_user_id=admin.id,
        metadata={"actions": actions},
    )
    await db.commit()
    await db.refresh(discussion)
    return to_discussion(discussion, admin)


async def list_reports(
    db: AsyncSession, page: int, page_size: int, report_status: str | None
) -> ContentReportPage:
    filters = []
    if report_status is not None:
        filters.append(ContentReport.status == report_status)
    total = int(await db.scalar(select(func.count(ContentReport.id)).where(*filters)) or 0)
    reports = (
        await db.scalars(
            select(ContentReport)
            .where(*filters)
            .order_by(ContentReport.created_at.desc(), ContentReport.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return ContentReportPage(
        items=[
            ContentReportPublic(
                id=report.id,
                reporter_id=str(report.reporter_id) if report.reporter_id else None,
                discussion_id=report.discussion_id,
                comment_id=report.comment_id,
                reason=report.reason,
                status=report.status,
                created_at=report.created_at,
            )
            for report in reports
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def handle_report(
    db: AsyncSession,
    report_id: int,
    admin: User,
    report_status: str,
    reason: str | None,
) -> ContentReportPublic:
    report = await db.get(ContentReport, report_id)
    if report is None:
        raise content_error(404, "REPORT_NOT_FOUND", "举报不存在")
    report.status = report_status
    report.handled_by = admin.id
    report.handled_at = datetime.now(timezone.utc)
    add_moderation_action(db, admin.id, "report", report.id, report_status, reason)
    record_audit(
        db,
        action="report.handle",
        target_type="report",
        target_id=report.id,
        actor_user_id=admin.id,
        metadata={"status": report_status, "reason_provided": bool(reason)},
    )
    await db.commit()
    return ContentReportPublic(
        id=report.id,
        reporter_id=str(report.reporter_id) if report.reporter_id else None,
        discussion_id=report.discussion_id,
        comment_id=report.comment_id,
        reason=report.reason,
        status=report.status,
        created_at=report.created_at,
    )
