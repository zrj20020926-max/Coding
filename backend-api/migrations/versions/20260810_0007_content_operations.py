# ruff: noqa: E501
"""Add content operations, moderation, reports, and safe deletion semantics.

Revision ID: 20260810_0007
Revises: 20260809_0006
Create Date: 2026-08-10
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260810_0007"
down_revision: Optional[str] = "20260809_0006"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE content_review_status AS ENUM "
        "('pending', 'approved', 'rejected')"
    )
    op.execute(
        "ALTER TABLE collections ADD COLUMN created_by UUID "
        "REFERENCES users(id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX idx_collections_public_created ON collections (created_at DESC, id DESC) WHERE is_public")
    op.execute(
        "CREATE INDEX idx_collection_problems_sequence "
        "ON collection_problems (collection_id, sequence, problem_id)"
    )

    op.execute("ALTER TABLE discussions ALTER COLUMN user_id DROP NOT NULL")
    op.execute("ALTER TABLE discussions DROP CONSTRAINT discussions_user_id_fkey")
    op.execute(
        "ALTER TABLE discussions ADD CONSTRAINT discussions_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE discussions ADD COLUMN comment_count INTEGER NOT NULL DEFAULT 0 "
        "CONSTRAINT ck_discussion_comment_count CHECK (comment_count >= 0)"
    )
    op.execute(
        "ALTER TABLE discussions ADD COLUMN report_count INTEGER NOT NULL DEFAULT 0 "
        "CONSTRAINT ck_discussion_report_count CHECK (report_count >= 0)"
    )
    op.execute("ALTER TABLE discussions ADD COLUMN review_status content_review_status NOT NULL DEFAULT 'approved'")
    op.execute("ALTER TABLE discussions ADD COLUMN moderation_reason VARCHAR(500)")
    op.execute("ALTER TABLE discussions ADD COLUMN moderated_by UUID REFERENCES users(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE discussions ADD COLUMN moderated_at TIMESTAMPTZ")
    op.execute("ALTER TABLE discussions ADD COLUMN deleted_at TIMESTAMPTZ")

    op.execute("ALTER TABLE discussion_comments ALTER COLUMN user_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE discussion_comments DROP CONSTRAINT discussion_comments_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE discussion_comments ADD CONSTRAINT discussion_comments_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE discussion_comments ADD COLUMN depth SMALLINT NOT NULL DEFAULT 0 "
        "CONSTRAINT ck_comment_depth CHECK (depth BETWEEN 0 AND 3)"
    )
    op.execute(
        "ALTER TABLE discussion_comments ADD COLUMN report_count INTEGER NOT NULL DEFAULT 0 "
        "CONSTRAINT ck_comment_report_count CHECK (report_count >= 0)"
    )
    op.execute("ALTER TABLE discussion_comments ADD COLUMN review_status content_review_status NOT NULL DEFAULT 'approved'")
    op.execute("ALTER TABLE discussion_comments ADD COLUMN moderation_reason VARCHAR(500)")
    op.execute("ALTER TABLE discussion_comments ADD COLUMN moderated_by UUID REFERENCES users(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE discussion_comments ADD COLUMN moderated_at TIMESTAMPTZ")
    op.execute("ALTER TABLE discussion_comments ADD COLUMN deleted_at TIMESTAMPTZ")

    op.execute(
        "CREATE INDEX idx_discussions_public_order ON discussions "
        "(problem_id, is_pinned DESC, created_at DESC, id DESC) "
        "WHERE deleted_at IS NULL AND review_status = 'approved'"
    )
    op.execute(
        "CREATE INDEX idx_comments_public_order ON discussion_comments "
        "(discussion_id, created_at, id) "
        "WHERE review_status = 'approved'"
    )

    op.execute(
        """
        CREATE TABLE content_reports (
            id BIGSERIAL PRIMARY KEY,
            reporter_id UUID REFERENCES users(id) ON DELETE SET NULL,
            discussion_id BIGINT REFERENCES discussions(id) ON DELETE CASCADE,
            comment_id BIGINT REFERENCES discussion_comments(id) ON DELETE CASCADE,
            reason VARCHAR(500) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            handled_by UUID REFERENCES users(id) ON DELETE SET NULL,
            handled_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_content_report_status CHECK (
                status IN ('pending', 'resolved', 'dismissed')
            ),
            CONSTRAINT ck_content_report_one_target CHECK (
                (discussion_id IS NOT NULL)::integer +
                (comment_id IS NOT NULL)::integer = 1
            )
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_reports_user_discussion ON content_reports "
        "(reporter_id, discussion_id) WHERE discussion_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_reports_user_comment ON content_reports "
        "(reporter_id, comment_id) WHERE comment_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_content_reports_pending ON content_reports (created_at, id) "
        "WHERE status = 'pending'"
    )
    op.execute(
        """
        CREATE TABLE content_moderation_actions (
            id BIGSERIAL PRIMARY KEY,
            admin_id UUID REFERENCES users(id) ON DELETE SET NULL,
            target_type VARCHAR(20) NOT NULL,
            target_id BIGINT NOT NULL,
            action VARCHAR(30) NOT NULL,
            reason VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_moderation_action_target_type CHECK (
                target_type IN ('discussion', 'comment', 'report')
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_moderation_actions_target ON content_moderation_actions "
        "(target_type, target_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS content_moderation_actions")
    op.execute("DROP TABLE IF EXISTS content_reports")
    op.execute("DROP INDEX IF EXISTS idx_comments_public_order")
    op.execute("DROP INDEX IF EXISTS idx_discussions_public_order")
    for column in (
        "deleted_at",
        "moderated_at",
        "moderated_by",
        "moderation_reason",
        "review_status",
        "report_count",
        "depth",
    ):
        op.execute(f"ALTER TABLE discussion_comments DROP COLUMN IF EXISTS {column}")
    for column in (
        "deleted_at",
        "moderated_at",
        "moderated_by",
        "moderation_reason",
        "review_status",
        "report_count",
        "comment_count",
    ):
        op.execute(f"ALTER TABLE discussions DROP COLUMN IF EXISTS {column}")
    # Migration 0006 required authors and used cascading user deletion. Rows whose
    # author was removed while 0007 was active cannot satisfy that older contract.
    op.execute("DELETE FROM discussion_comments WHERE user_id IS NULL")
    op.execute("DELETE FROM discussions WHERE user_id IS NULL")
    op.execute(
        "ALTER TABLE discussion_comments DROP CONSTRAINT discussion_comments_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE discussion_comments ADD CONSTRAINT discussion_comments_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute("ALTER TABLE discussion_comments ALTER COLUMN user_id SET NOT NULL")
    op.execute("ALTER TABLE discussions DROP CONSTRAINT discussions_user_id_fkey")
    op.execute(
        "ALTER TABLE discussions ADD CONSTRAINT discussions_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
    )
    op.execute("ALTER TABLE discussions ALTER COLUMN user_id SET NOT NULL")
    op.execute("DROP INDEX IF EXISTS idx_collection_problems_sequence")
    op.execute("DROP INDEX IF EXISTS idx_collections_public_created")
    op.execute("ALTER TABLE collections DROP COLUMN IF EXISTS created_by")
    op.execute("DROP TYPE IF EXISTS content_review_status")
