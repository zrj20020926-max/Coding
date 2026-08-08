"""Add the reliable submission control plane.

Revision ID: 20260808_0004
Revises: 20260808_0003
Create Date: 2026-08-08
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260808_0004"
down_revision: Optional[str] = "20260808_0003"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute("ALTER TABLE submissions ADD COLUMN idempotency_key VARCHAR(128)")
    op.execute("ALTER TABLE submissions ADD COLUMN request_fingerprint CHAR(64)")
    op.execute(
        "ALTER TABLE submissions ADD CONSTRAINT ck_submissions_idempotency_fingerprint "
        "CHECK (idempotency_key IS NULL OR request_fingerprint IS NOT NULL)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_submissions_user_idempotency_key "
        "ON submissions (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL"
    )
    op.execute(
        """
        CREATE TABLE outbox_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            aggregate_type VARCHAR(50) NOT NULL,
            aggregate_id UUID NOT NULL,
            event_type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            published_at TIMESTAMPTZ,
            stream_message_id TEXT,
            last_error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_outbox_unpublished_retry ON outbox_events (next_attempt_at, created_at) "
        "WHERE published_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_outbox_aggregate ON outbox_events (aggregate_type, aggregate_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_outbox_stream_message ON outbox_events (stream_message_id) "
        "WHERE stream_message_id IS NOT NULL"
    )
    op.execute(
        """
        CREATE FUNCTION enforce_submission_status_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.status = OLD.status THEN
                RETURN NEW;
            END IF;

            IF (OLD.status = 'Pending' AND NEW.status = 'Compiling')
               OR (OLD.status = 'Compiling' AND NEW.status IN (
                    'Running', 'Compile Error', 'System Error'
               ))
               OR (OLD.status = 'Running' AND NEW.status IN (
                    'Accepted', 'Wrong Answer', 'Runtime Error', 'Time Limit Exceeded',
                    'Memory Limit Exceeded', 'System Error'
               )) THEN
                RETURN NEW;
            END IF;

            RAISE EXCEPTION 'invalid submission status transition: % -> %', OLD.status, NEW.status
                USING ERRCODE = '23514';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_submissions_status_transition "
        "BEFORE UPDATE OF status ON submissions FOR EACH ROW "
        "EXECUTE FUNCTION enforce_submission_status_transition()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_submissions_status_transition ON submissions")
    op.execute("DROP FUNCTION IF EXISTS enforce_submission_status_transition()")
    op.execute("DROP TABLE IF EXISTS outbox_events")
    op.execute("DROP INDEX IF EXISTS uq_submissions_user_idempotency_key")
    op.execute(
        "ALTER TABLE submissions DROP CONSTRAINT IF EXISTS ck_submissions_idempotency_fingerprint"
    )
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS request_fingerprint")
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS idempotency_key")
