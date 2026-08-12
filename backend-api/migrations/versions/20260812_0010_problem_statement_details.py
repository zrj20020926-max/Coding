"""Add structured constraints and sample explanation to problem statements.

Revision ID: 20260812_0010
Revises: 20260812_0009
Create Date: 2026-08-12
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260812_0010"
down_revision: Optional[str] = "20260812_0009"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute("ALTER TABLE problems ADD COLUMN data_constraints TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE problems ADD COLUMN sample_explanation TEXT NOT NULL DEFAULT ''")


def downgrade() -> None:
    op.execute("ALTER TABLE problems DROP COLUMN sample_explanation")
    op.execute("ALTER TABLE problems DROP COLUMN data_constraints")
