"""Add the public problem catalog pagination index.

Revision ID: 20260808_0003
Revises: 20260808_0002
Create Date: 2026-08-08
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260808_0003"
down_revision: Optional[str] = "20260808_0002"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_problems_public_created "
        "ON problems (created_at DESC, id DESC) WHERE visibility = 'public'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_problems_public_created")
