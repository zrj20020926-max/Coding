# ruff: noqa: UP045
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.problem import Problem, enum_values, problem_id_type
from app.models.user import User

content_id_type = BigInteger().with_variant(Integer, "sqlite")


class ContentReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


review_status_type = Enum(
    ContentReviewStatus,
    name="content_review_status",
    values_callable=enum_values,
    validate_strings=True,
)


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(content_id_type, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    company: Mapped[Optional[str]] = mapped_column(String(50))
    cover_url: Mapped[Optional[str]] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list[CollectionProblem]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="CollectionProblem.sequence",
        lazy="selectin",
    )


class CollectionProblem(Base):
    __tablename__ = "collection_problems"
    __table_args__ = (
        UniqueConstraint("collection_id", "sequence", name="uq_collection_sequence"),
    )

    collection_id: Mapped[int] = mapped_column(
        content_id_type,
        ForeignKey("collections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    problem_id: Mapped[int] = mapped_column(
        problem_id_type,
        ForeignKey("problems.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    collection: Mapped[Collection] = relationship(back_populates="items")
    problem: Mapped[Problem] = relationship(lazy="joined")


class DailyChallenge(Base):
    __tablename__ = "daily_challenges"

    challenge_date: Mapped[date] = mapped_column(Date, primary_key=True)
    problem_id: Mapped[int] = mapped_column(
        problem_id_type,
        ForeignKey("problems.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    problem: Mapped[Problem] = relationship(lazy="joined")


class Discussion(Base):
    __tablename__ = "discussions"
    __table_args__ = (
        CheckConstraint("comment_count >= 0", name="ck_discussion_comment_count"),
        CheckConstraint("report_count >= 0", name="ck_discussion_report_count"),
    )

    id: Mapped[int] = mapped_column(content_id_type, primary_key=True, autoincrement=True)
    problem_id: Mapped[int] = mapped_column(
        problem_id_type,
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_status: Mapped[ContentReviewStatus] = mapped_column(
        review_status_type, nullable=False, default=ContentReviewStatus.APPROVED
    )
    moderation_reason: Mapped[Optional[str]] = mapped_column(String(500))
    moderated_by: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    author: Mapped[Optional[User]] = relationship(foreign_keys=[user_id], lazy="joined")


class DiscussionComment(Base):
    __tablename__ = "discussion_comments"
    __table_args__ = (
        CheckConstraint("depth BETWEEN 0 AND 3", name="ck_comment_depth"),
        CheckConstraint("report_count >= 0", name="ck_comment_report_count"),
    )

    id: Mapped[int] = mapped_column(content_id_type, primary_key=True, autoincrement=True)
    discussion_id: Mapped[int] = mapped_column(
        content_id_type,
        ForeignKey("discussions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        content_id_type, ForeignKey("discussion_comments.id", ondelete="CASCADE")
    )
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_status: Mapped[ContentReviewStatus] = mapped_column(
        review_status_type, nullable=False, default=ContentReviewStatus.APPROVED
    )
    moderation_reason: Mapped[Optional[str]] = mapped_column(String(500))
    moderated_by: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    author: Mapped[Optional[User]] = relationship(foreign_keys=[user_id], lazy="joined")


class ContentReport(Base):
    __tablename__ = "content_reports"
    __table_args__ = (
        CheckConstraint(
            "(discussion_id IS NULL) <> (comment_id IS NULL)",
            name="ck_content_report_one_target",
        ),
        CheckConstraint(
            "status IN ('pending', 'resolved', 'dismissed')",
            name="ck_content_report_status",
        ),
    )

    id: Mapped[int] = mapped_column(content_id_type, primary_key=True, autoincrement=True)
    reporter_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    discussion_id: Mapped[Optional[int]] = mapped_column(
        content_id_type, ForeignKey("discussions.id", ondelete="CASCADE")
    )
    comment_id: Mapped[Optional[int]] = mapped_column(
        content_id_type, ForeignKey("discussion_comments.id", ondelete="CASCADE")
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    handled_by: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    handled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ContentModerationAction(Base):
    __tablename__ = "content_moderation_actions"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('discussion', 'comment', 'report')",
            name="ck_moderation_action_target_type",
        ),
    )

    id: Mapped[int] = mapped_column(content_id_type, primary_key=True, autoincrement=True)
    admin_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(content_id_type, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Index(
    "idx_collections_public_created",
    Collection.created_at,
    Collection.id,
    postgresql_where=Collection.is_public.is_(True),
    sqlite_where=Collection.is_public.is_(True),
)
Index(
    "idx_collection_problems_sequence",
    CollectionProblem.collection_id,
    CollectionProblem.sequence,
    CollectionProblem.problem_id,
)
Index(
    "uq_reports_user_discussion",
    ContentReport.reporter_id,
    ContentReport.discussion_id,
    unique=True,
    postgresql_where=ContentReport.discussion_id.is_not(None),
    sqlite_where=ContentReport.discussion_id.is_not(None),
)
Index(
    "uq_reports_user_comment",
    ContentReport.reporter_id,
    ContentReport.comment_id,
    unique=True,
    postgresql_where=ContentReport.comment_id.is_not(None),
    sqlite_where=ContentReport.comment_id.is_not(None),
)
Index(
    "idx_discussions_public_order",
    Discussion.problem_id,
    Discussion.is_pinned.desc(),
    Discussion.created_at.desc(),
    Discussion.id.desc(),
    postgresql_where=(
        Discussion.deleted_at.is_(None)
        & (Discussion.review_status == ContentReviewStatus.APPROVED)
    ),
    sqlite_where=(
        Discussion.deleted_at.is_(None)
        & (Discussion.review_status == ContentReviewStatus.APPROVED)
    ),
)
Index(
    "idx_comments_public_order",
    DiscussionComment.discussion_id,
    DiscussionComment.created_at,
    DiscussionComment.id,
    postgresql_where=(
        DiscussionComment.review_status == ContentReviewStatus.APPROVED
    ),
    sqlite_where=(DiscussionComment.review_status == ContentReviewStatus.APPROVED),
)
Index(
    "idx_content_reports_pending",
    ContentReport.created_at,
    ContentReport.id,
    postgresql_where=(ContentReport.status == "pending"),
    sqlite_where=(ContentReport.status == "pending"),
)
Index(
    "idx_moderation_actions_target",
    ContentModerationAction.target_type,
    ContentModerationAction.target_id,
    ContentModerationAction.created_at.desc(),
)
