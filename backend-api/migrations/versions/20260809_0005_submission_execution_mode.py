"""Add sample and formal judge execution modes.

Revision ID: 20260809_0005
Revises: 20260808_0004
Create Date: 2026-08-09
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260809_0005"
down_revision: Optional[str] = "20260808_0004"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute("CREATE TYPE submission_mode AS ENUM ('sample', 'judge')")
    op.execute(
        "ALTER TABLE submissions ADD COLUMN mode submission_mode "
        "NOT NULL DEFAULT 'judge'"
    )
    op.execute("ALTER TABLE submissions ADD COLUMN sample_output TEXT")
    op.execute(
        "CREATE INDEX idx_submissions_user_mode_created "
        "ON submissions (user_id, mode, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_submissions_user_mode_created")
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS sample_output")
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS mode")
    op.execute("DROP TYPE IF EXISTS submission_mode")
