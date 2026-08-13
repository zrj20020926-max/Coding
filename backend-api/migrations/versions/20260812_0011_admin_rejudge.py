"""Add auditable administrator rejudge tasks.

Revision ID: 20260812_0011
Revises: 20260812_0010
Create Date: 2026-08-12
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260812_0011"
down_revision: Optional[str] = "20260812_0010"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE submissions ADD COLUMN is_rejudge BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE submissions ADD COLUMN original_submission_id UUID "
        "REFERENCES submissions(id) ON DELETE RESTRICT"
    )
    op.execute(
        """
        CREATE TABLE rejudge_tasks (
            id UUID PRIMARY KEY,
            requested_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            mode VARCHAR(20) NOT NULL,
            problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE RESTRICT,
            test_set_id UUID NOT NULL REFERENCES test_sets(id) ON DELETE RESTRICT,
            total_count INTEGER NOT NULL CHECK (total_count > 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_rejudge_task_mode CHECK (mode IN ('single', 'batch'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE rejudge_task_items (
            task_id UUID NOT NULL REFERENCES rejudge_tasks(id) ON DELETE CASCADE,
            original_submission_id UUID NOT NULL REFERENCES submissions(id) ON DELETE RESTRICT,
            rejudge_submission_id UUID NOT NULL REFERENCES submissions(id) ON DELETE RESTRICT,
            PRIMARY KEY (task_id, original_submission_id),
            CONSTRAINT uq_rejudge_item_submission UNIQUE (rejudge_submission_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_rejudge_tasks_created ON rejudge_tasks (created_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX idx_rejudge_items_task ON rejudge_task_items (task_id, rejudge_submission_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rejudge_task_items")
    op.execute("DROP TABLE IF EXISTS rejudge_tasks")
    op.execute("ALTER TABLE submissions DROP COLUMN original_submission_id")
    op.execute("ALTER TABLE submissions DROP COLUMN is_rejudge")
