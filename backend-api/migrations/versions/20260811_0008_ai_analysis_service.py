# ruff: noqa: E501
"""Add the isolated AI analysis control plane, usage ledger, and audit log.

Revision ID: 20260811_0008
Revises: 20260810_0007
Create Date: 2026-08-11
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260811_0008"
down_revision: Optional[str] = "20260810_0007"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute("ALTER TABLE ai_analyses ADD COLUMN user_id UUID REFERENCES users(id) ON DELETE CASCADE")
    op.execute(
        "UPDATE ai_analyses a SET user_id = s.user_id FROM submissions s "
        "WHERE s.id = a.submission_id"
    )
    op.execute("ALTER TABLE ai_analyses ALTER COLUMN user_id SET NOT NULL")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN request_fingerprint CHAR(64)")
    op.execute(
        "UPDATE ai_analyses SET request_fingerprint = encode(digest(submission_id::text, 'sha256'), 'hex')"
    )
    op.execute("ALTER TABLE ai_analyses ALTER COLUMN request_fingerprint SET NOT NULL")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN failure_summary TEXT")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN guiding_questions JSONB")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN confidence VARCHAR(10)")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN provider VARCHAR(50)")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN total_cost_microusd BIGINT NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN latency_ms INTEGER")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN provider_request_id VARCHAR(200)")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN cached_from_id UUID REFERENCES ai_analyses(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN error_code VARCHAR(50)")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN started_at TIMESTAMPTZ")
    op.execute("ALTER TABLE ai_analyses ADD COLUMN completed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE ai_analyses ADD CONSTRAINT ck_ai_analyses_retry_count CHECK (retry_count >= 0)")
    op.execute("ALTER TABLE ai_analyses ADD CONSTRAINT ck_ai_analyses_cost CHECK (total_cost_microusd >= 0)")
    op.execute("ALTER TABLE ai_analyses ADD CONSTRAINT ck_ai_analyses_confidence CHECK (confidence IS NULL OR confidence IN ('low', 'medium', 'high'))")
    op.execute("CREATE INDEX idx_ai_analyses_user_created ON ai_analyses (user_id, created_at DESC)")
    op.execute("CREATE INDEX idx_ai_analyses_retryable ON ai_analyses (created_at) WHERE status IN ('pending', 'running')")
    op.execute("CREATE INDEX idx_ai_analyses_completed_fingerprint ON ai_analyses (request_fingerprint, completed_at DESC) WHERE status = 'completed'")

    op.execute(
        """
        CREATE TABLE ai_usage_records (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            analysis_id UUID NOT NULL UNIQUE REFERENCES ai_analyses(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider VARCHAR(50),
            model_name VARCHAR(100),
            prompt_tokens INTEGER NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
            completion_tokens INTEGER NOT NULL DEFAULT 0 CHECK (completion_tokens >= 0),
            input_cost_microusd BIGINT NOT NULL DEFAULT 0 CHECK (input_cost_microusd >= 0),
            output_cost_microusd BIGINT NOT NULL DEFAULT 0 CHECK (output_cost_microusd >= 0),
            total_cost_microusd BIGINT NOT NULL DEFAULT 0 CHECK (total_cost_microusd >= 0),
            cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_ai_usage_user_created ON ai_usage_records (user_id, created_at DESC)")
    op.execute(
        """
        CREATE TABLE audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            action VARCHAR(100) NOT NULL,
            target_type VARCHAR(50) NOT NULL,
            target_id VARCHAR(100),
            request_id VARCHAR(100),
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_audit_logs_actor_created ON audit_logs (actor_user_id, created_at DESC)")
    op.execute("CREATE INDEX idx_audit_logs_target_created ON audit_logs (target_type, target_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_logs")
    op.execute("DROP TABLE IF EXISTS ai_usage_records")
    op.execute("DROP INDEX IF EXISTS idx_ai_analyses_completed_fingerprint")
    op.execute("DROP INDEX IF EXISTS idx_ai_analyses_retryable")
    op.execute("DROP INDEX IF EXISTS idx_ai_analyses_user_created")
    for column in (
        "completed_at", "started_at", "error_code", "cached_from_id", "retry_count",
        "provider_request_id", "latency_ms", "total_cost_microusd", "provider", "confidence",
        "guiding_questions", "failure_summary", "request_fingerprint", "user_id",
    ):
        op.execute(f"ALTER TABLE ai_analyses DROP COLUMN IF EXISTS {column}")
