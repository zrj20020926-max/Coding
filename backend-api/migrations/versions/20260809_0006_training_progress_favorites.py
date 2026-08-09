"""Add idempotent training statistics ledger and favorite indexes.

Revision ID: 20260809_0006
Revises: 20260809_0005
Create Date: 2026-08-09
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260809_0006"
down_revision: Optional[str] = "20260809_0005"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE submission_stat_events (
            submission_id UUID PRIMARY KEY
                REFERENCES submissions(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
            terminal_status submission_status NOT NULL,
            accepted BOOLEAN NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_stat_event_terminal_status CHECK (
                terminal_status IN (
                    'Accepted', 'Wrong Answer', 'Compile Error', 'Runtime Error',
                    'Time Limit Exceeded', 'Memory Limit Exceeded', 'System Error'
                )
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_stat_events_user_applied "
        "ON submission_stat_events (user_id, applied_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_stat_events_problem_applied "
        "ON submission_stat_events (problem_id, applied_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_favorites_user_created "
        "ON favorites (user_id, created_at DESC, problem_id)"
    )
    op.execute("CREATE INDEX idx_favorites_problem ON favorites (problem_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_favorites_problem")
    op.execute("DROP INDEX IF EXISTS idx_favorites_user_created")
    op.execute("DROP TABLE IF EXISTS submission_stat_events")
