"""Add structured JavaScript ACM input/output diagnostics.

Revision ID: 20260815_0018
Revises: 20260814_0017
Create Date: 2026-08-15
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260815_0018"
down_revision: Optional[str] = "20260814_0017"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute("ALTER TABLE ai_analyses ADD COLUMN diagnostic_report JSONB")
    op.execute(
        "ALTER TABLE ai_analyses ADD CONSTRAINT ck_ai_diagnostic_report_object "
        "CHECK (diagnostic_report IS NULL OR jsonb_typeof(diagnostic_report) = 'object')"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE ai_analyses DROP CONSTRAINT IF EXISTS ck_ai_diagnostic_report_object"
    )
    op.execute("ALTER TABLE ai_analyses DROP COLUMN IF EXISTS diagnostic_report")
