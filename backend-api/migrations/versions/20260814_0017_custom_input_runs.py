"""Add isolated custom stdin runs.

Revision ID: 20260814_0017
Revises: 20260814_0016
Create Date: 2026-08-14
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260814_0017"
down_revision: Optional[str] = "20260814_0016"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def _snapshot_function(custom_fields: bool) -> str:
    custom_checks = """
               OR NEW.custom_input_object_key IS DISTINCT FROM OLD.custom_input_object_key
               OR NEW.custom_input_checksum IS DISTINCT FROM OLD.custom_input_checksum
               OR NEW.custom_input_size_bytes IS DISTINCT FROM OLD.custom_input_size_bytes
    """ if custom_fields else ""
    return f"""
        CREATE OR REPLACE FUNCTION protect_submission_snapshot()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.problem_id <> OLD.problem_id
               OR NEW.test_set_id IS DISTINCT FROM OLD.test_set_id
               OR NEW.problem_version <> OLD.problem_version
               OR NEW.time_limit_ms_snapshot <> OLD.time_limit_ms_snapshot
               OR NEW.memory_limit_mb_snapshot <> OLD.memory_limit_mb_snapshot
               OR NEW.mode <> OLD.mode
               {custom_checks} THEN
                RAISE EXCEPTION 'submission judge snapshot is immutable'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """


def upgrade() -> None:
    # PostgreSQL rejects use of a newly added enum value in a constraint until
    # the enum alteration commits, so isolate it in Alembic's autocommit block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE submission_mode ADD VALUE IF NOT EXISTS 'custom'")
    op.execute("ALTER TABLE submissions ADD COLUMN custom_input_object_key TEXT")
    op.execute("ALTER TABLE submissions ADD COLUMN custom_input_checksum CHAR(64)")
    op.execute("ALTER TABLE submissions ADD COLUMN custom_input_size_bytes INTEGER")
    op.execute("ALTER TABLE submissions DROP CONSTRAINT ck_submissions_test_set_mode")
    op.execute(
        "ALTER TABLE submissions ADD CONSTRAINT ck_submissions_test_set_mode CHECK ("
        "(mode IN ('sample', 'custom') AND test_set_id IS NULL) OR "
        "(mode = 'judge' AND test_set_id IS NOT NULL))"
    )
    op.execute(
        "ALTER TABLE submissions ADD CONSTRAINT ck_submissions_custom_input_mode CHECK ("
        "(mode = 'custom' AND custom_input_object_key IS NOT NULL "
        "AND custom_input_checksum IS NOT NULL AND custom_input_size_bytes IS NOT NULL "
        "AND custom_input_size_bytes >= 0) OR "
        "(mode <> 'custom' AND custom_input_object_key IS NULL "
        "AND custom_input_checksum IS NULL AND custom_input_size_bytes IS NULL))"
    )
    op.execute(_snapshot_function(custom_fields=True))


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM submissions WHERE mode = 'custom') THEN
                RAISE EXCEPTION 'cannot downgrade while custom submissions exist';
            END IF;
        END
        $$
        """
    )
    op.execute(_snapshot_function(custom_fields=False))
    op.execute("ALTER TABLE submissions DROP CONSTRAINT ck_submissions_custom_input_mode")
    op.execute("ALTER TABLE submissions DROP CONSTRAINT ck_submissions_test_set_mode")
    for column in (
        "custom_input_size_bytes",
        "custom_input_checksum",
        "custom_input_object_key",
    ):
        op.execute(f"ALTER TABLE submissions DROP COLUMN {column}")
    op.execute("ALTER TABLE submissions ALTER COLUMN mode DROP DEFAULT")
    op.execute("ALTER TABLE submissions ALTER COLUMN mode TYPE TEXT USING mode::text")
    op.execute("DROP TYPE submission_mode")
    op.execute("CREATE TYPE submission_mode AS ENUM ('sample', 'judge')")
    op.execute(
        "ALTER TABLE submissions ALTER COLUMN mode TYPE submission_mode "
        "USING mode::submission_mode"
    )
    op.execute("ALTER TABLE submissions ALTER COLUMN mode SET DEFAULT 'judge'")
    op.execute(
        "ALTER TABLE submissions ADD CONSTRAINT ck_submissions_test_set_mode CHECK ("
        "(mode = 'sample' AND test_set_id IS NULL) OR "
        "(mode = 'judge' AND test_set_id IS NOT NULL))"
    )
