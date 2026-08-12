# ruff: noqa: E501
"""Add immutable versioned test sets and submission judge snapshots.

Revision ID: 20260812_0009
Revises: 20260811_0008
Create Date: 2026-08-12
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260812_0009"
down_revision: Optional[str] = "20260811_0008"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute("CREATE TYPE test_set_status AS ENUM ('draft', 'validating', 'ready', 'active', 'inactive', 'invalid')")
    op.execute("CREATE TYPE checker_type AS ENUM ('exact', 'token', 'float')")
    op.execute("ALTER TABLE problems ADD COLUMN version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0)")
    op.execute(
        """
        CREATE TABLE test_sets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE CASCADE,
            version INTEGER NOT NULL CHECK (version > 0),
            status test_set_status NOT NULL DEFAULT 'draft',
            checker_type checker_type NOT NULL DEFAULT 'exact',
            absolute_tolerance NUMERIC(20, 10),
            relative_tolerance NUMERIC(20, 10),
            case_count INTEGER NOT NULL DEFAULT 0 CHECK (case_count >= 0),
            total_score NUMERIC(9, 2) NOT NULL DEFAULT 0 CHECK (total_score >= 0),
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            activated_at TIMESTAMPTZ,
            CONSTRAINT uq_test_sets_problem_version UNIQUE (problem_id, version),
            CONSTRAINT uq_test_sets_id_problem UNIQUE (id, problem_id),
            CONSTRAINT ck_test_sets_checker_config CHECK (
                (checker_type IN ('exact', 'token') AND absolute_tolerance IS NULL AND relative_tolerance IS NULL)
                OR
                (checker_type = 'float' AND absolute_tolerance IS NOT NULL
                 AND relative_tolerance IS NOT NULL AND absolute_tolerance >= 0
                 AND relative_tolerance >= 0
                 AND (absolute_tolerance > 0 OR relative_tolerance > 0))
            )
        )
        """
    )
    op.execute("CREATE INDEX idx_test_sets_problem_version ON test_sets (problem_id, version DESC)")
    op.execute("CREATE UNIQUE INDEX uq_test_sets_active_problem ON test_sets (problem_id) WHERE status = 'active'")

    # Every existing problem receives a stable legacy version. Problems with hidden cases
    # become active; empty legacy versions remain inactive and therefore fail publication.
    op.execute(
        """
        INSERT INTO test_sets (problem_id, version, status, checker_type, case_count, total_score, activated_at)
        SELECT p.id, 1,
               CASE WHEN count(tc.id) > 0 AND COALESCE(sum(tc.score), 0) = 100
                          AND count(tc.id) FILTER (WHERE tc.score <= 0) = 0
                    THEN 'active'::test_set_status
                    ELSE 'inactive'::test_set_status END,
               'exact'::checker_type, count(tc.id), COALESCE(sum(tc.score), 0),
               CASE WHEN count(tc.id) > 0 AND COALESCE(sum(tc.score), 0) = 100
                          AND count(tc.id) FILTER (WHERE tc.score <= 0) = 0
                    THEN now() ELSE NULL END
          FROM problems p
          LEFT JOIN test_cases tc ON tc.problem_id = p.id AND tc.is_hidden
         GROUP BY p.id
        """
    )
    # Some legacy databases stored public/sample rows in test_cases as well. Preserve
    # those rows (and any submission_case_results FKs) in a separate inactive archive;
    # they must never become part of the hidden set used by formal submissions.
    op.execute(
        """
        INSERT INTO test_sets (problem_id, version, status, checker_type, case_count, total_score)
        SELECT p.id, 2, 'inactive'::test_set_status, 'exact'::checker_type,
               count(tc.id), COALESCE(sum(tc.score), 0)
          FROM problems p
          JOIN test_cases tc ON tc.problem_id = p.id AND NOT tc.is_hidden
         GROUP BY p.id
        """
    )
    op.execute(
        "UPDATE problems p SET visibility = 'draft' "
        "WHERE p.visibility = 'public' AND NOT EXISTS ("
        "SELECT 1 FROM test_sets ts WHERE ts.problem_id = p.id AND ts.status = 'active')"
    )

    op.execute("ALTER TABLE test_cases ADD COLUMN test_set_id UUID REFERENCES test_sets(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE test_cases ADD COLUMN input_size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (input_size_bytes >= 0)")
    op.execute("ALTER TABLE test_cases ADD COLUMN output_size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (output_size_bytes >= 0)")
    op.execute(
        "UPDATE test_cases tc SET test_set_id = ts.id FROM test_sets ts "
        "WHERE ts.problem_id = tc.problem_id "
        "AND ts.version = CASE WHEN tc.is_hidden THEN 1 ELSE 2 END"
    )
    op.execute("ALTER TABLE test_cases ALTER COLUMN test_set_id SET NOT NULL")
    op.execute("ALTER TABLE test_cases DROP CONSTRAINT IF EXISTS test_cases_problem_id_sequence_key")
    op.execute("DROP INDEX IF EXISTS idx_test_cases_problem")
    op.execute("ALTER TABLE test_cases ADD CONSTRAINT uq_test_cases_set_sequence UNIQUE (test_set_id, sequence)")
    op.execute("CREATE INDEX idx_test_cases_test_set_sequence ON test_cases (test_set_id, sequence)")
    op.execute("ALTER TABLE test_cases DROP COLUMN problem_id")
    op.execute("ALTER TABLE test_cases DROP COLUMN is_sample")
    op.execute("ALTER TABLE test_cases DROP COLUMN is_hidden")

    op.execute("ALTER TABLE submissions ADD COLUMN test_set_id UUID")
    op.execute("ALTER TABLE submissions ADD COLUMN problem_version INTEGER NOT NULL DEFAULT 1 CHECK (problem_version > 0)")
    op.execute("ALTER TABLE submissions ADD COLUMN time_limit_ms_snapshot INTEGER")
    op.execute("ALTER TABLE submissions ADD COLUMN memory_limit_mb_snapshot INTEGER")
    op.execute(
        """
        UPDATE submissions s
           SET test_set_id = CASE WHEN s.mode = 'judge' THEN ts.id ELSE NULL END,
               problem_version = p.version,
               time_limit_ms_snapshot = p.time_limit_ms,
               memory_limit_mb_snapshot = p.memory_limit_mb
          FROM problems p
          JOIN test_sets ts ON ts.problem_id = p.id AND ts.version = 1
         WHERE p.id = s.problem_id
        """
    )
    op.execute("ALTER TABLE submissions ALTER COLUMN time_limit_ms_snapshot SET NOT NULL")
    op.execute("ALTER TABLE submissions ALTER COLUMN memory_limit_mb_snapshot SET NOT NULL")
    op.execute("ALTER TABLE submissions ADD CONSTRAINT fk_submissions_test_set_problem FOREIGN KEY (test_set_id, problem_id) REFERENCES test_sets(id, problem_id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE submissions ADD CONSTRAINT ck_submissions_test_set_mode CHECK ((mode = 'sample' AND test_set_id IS NULL) OR (mode = 'judge' AND test_set_id IS NOT NULL))")
    op.execute("CREATE INDEX idx_submissions_test_set ON submissions (test_set_id) WHERE test_set_id IS NOT NULL")
    # Existing unpublished events may contain the pre-snapshot execution payload. The
    # worker now reloads every immutable value from PostgreSQL, so keep only stable IDs.
    op.execute(
        """
        UPDATE outbox_events
           SET payload = jsonb_build_object(
               'event_id', id::text,
               'submission_id', aggregate_id::text
           )
         WHERE aggregate_type = 'submission'
           AND event_type = 'submission.created'
        """
    )

    op.execute(
        """
        CREATE FUNCTION refresh_test_set_totals()
        RETURNS TRIGGER AS $$
        DECLARE target_id UUID;
        BEGIN
            target_id := COALESCE(NEW.test_set_id, OLD.test_set_id);
            UPDATE test_sets
               SET case_count = (SELECT count(*) FROM test_cases WHERE test_set_id = target_id),
                   total_score = COALESCE((SELECT sum(score) FROM test_cases WHERE test_set_id = target_id), 0)
             WHERE id = target_id;
            IF TG_OP = 'UPDATE' AND OLD.test_set_id <> NEW.test_set_id THEN
                UPDATE test_sets
                   SET case_count = (SELECT count(*) FROM test_cases WHERE test_set_id = OLD.test_set_id),
                       total_score = COALESCE((SELECT sum(score) FROM test_cases WHERE test_set_id = OLD.test_set_id), 0)
                 WHERE id = OLD.test_set_id;
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("CREATE TRIGGER trg_test_cases_refresh_totals AFTER INSERT OR UPDATE OR DELETE ON test_cases FOR EACH ROW EXECUTE FUNCTION refresh_test_set_totals()")
    op.execute(
        """
        CREATE FUNCTION protect_test_set_mutation()
        RETURNS TRIGGER AS $$
        DECLARE referenced BOOLEAN;
        BEGIN
            referenced := EXISTS (SELECT 1 FROM submissions WHERE test_set_id = OLD.id);
            IF TG_OP = 'DELETE' THEN
                IF referenced THEN
                    RAISE EXCEPTION 'referenced test set cannot be deleted' USING ERRCODE = '23514';
                END IF;
                IF OLD.status <> 'draft' THEN
                    RAISE EXCEPTION 'only unreferenced draft test sets can be deleted' USING ERRCODE = '23514';
                END IF;
                RETURN OLD;
            END IF;
            IF referenced AND NOT (
                OLD.status = 'active' AND NEW.status = 'inactive'
                AND NEW.id = OLD.id AND NEW.problem_id = OLD.problem_id
                AND NEW.version = OLD.version AND NEW.checker_type = OLD.checker_type
                AND NEW.absolute_tolerance IS NOT DISTINCT FROM OLD.absolute_tolerance
                AND NEW.relative_tolerance IS NOT DISTINCT FROM OLD.relative_tolerance
                AND NEW.case_count = OLD.case_count AND NEW.total_score = OLD.total_score
                AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
                AND NEW.created_at = OLD.created_at
                AND NEW.activated_at IS NOT DISTINCT FROM OLD.activated_at
            ) THEN
                RAISE EXCEPTION 'referenced test set is immutable' USING ERRCODE = '23514';
            END IF;
            IF NEW.status IN ('ready', 'active') AND (NEW.case_count < 1 OR NEW.total_score <> 100) THEN
                RAISE EXCEPTION 'ready test set must contain cases totaling 100 points' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("CREATE TRIGGER trg_test_sets_protect BEFORE UPDATE OR DELETE ON test_sets FOR EACH ROW EXECUTE FUNCTION protect_test_set_mutation()")
    op.execute(
        """
        CREATE FUNCTION protect_test_case_mutation()
        RETURNS TRIGGER AS $$
        DECLARE target_id UUID; target_status test_set_status;
        BEGIN
            target_id := COALESCE(OLD.test_set_id, NEW.test_set_id);
            SELECT status INTO target_status FROM test_sets WHERE id = target_id;
            IF EXISTS (SELECT 1 FROM submissions WHERE test_set_id = target_id) THEN
                RAISE EXCEPTION 'cases in a referenced test set are immutable' USING ERRCODE = '23514';
            END IF;
            IF target_status NOT IN ('draft', 'invalid') THEN
                RAISE EXCEPTION 'cases can only change in draft or invalid test sets' USING ERRCODE = '23514';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("CREATE TRIGGER trg_test_cases_protect BEFORE INSERT OR UPDATE OR DELETE ON test_cases FOR EACH ROW EXECUTE FUNCTION protect_test_case_mutation()")
    op.execute(
        """
        CREATE FUNCTION protect_submission_snapshot()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.problem_id <> OLD.problem_id
               OR NEW.test_set_id IS DISTINCT FROM OLD.test_set_id
               OR NEW.problem_version <> OLD.problem_version
               OR NEW.time_limit_ms_snapshot <> OLD.time_limit_ms_snapshot
               OR NEW.memory_limit_mb_snapshot <> OLD.memory_limit_mb_snapshot
               OR NEW.mode <> OLD.mode THEN
                RAISE EXCEPTION 'submission judge snapshot is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("CREATE TRIGGER trg_submissions_snapshot_immutable BEFORE UPDATE ON submissions FOR EACH ROW EXECUTE FUNCTION protect_submission_snapshot()")
    op.execute(
        """
        CREATE FUNCTION increment_problem_version()
        RETURNS TRIGGER AS $$
        BEGIN
            IF ROW(NEW.title, NEW.description, NEW.difficulty, NEW.input_description,
                   NEW.output_description, NEW.sample_input, NEW.sample_output,
                   NEW.time_limit_ms, NEW.memory_limit_mb)
               IS DISTINCT FROM
               ROW(OLD.title, OLD.description, OLD.difficulty, OLD.input_description,
                   OLD.output_description, OLD.sample_input, OLD.sample_output,
                   OLD.time_limit_ms, OLD.memory_limit_mb) THEN
                NEW.version := OLD.version + 1;
            ELSIF NEW.version <> OLD.version THEN
                RAISE EXCEPTION 'problem version is managed automatically' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("CREATE TRIGGER trg_problems_version BEFORE UPDATE ON problems FOR EACH ROW EXECUTE FUNCTION increment_problem_version()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_problems_version ON problems")
    op.execute("DROP FUNCTION IF EXISTS increment_problem_version()")
    op.execute("DROP TRIGGER IF EXISTS trg_submissions_snapshot_immutable ON submissions")
    op.execute("DROP FUNCTION IF EXISTS protect_submission_snapshot()")
    op.execute("DROP TRIGGER IF EXISTS trg_test_cases_protect ON test_cases")
    op.execute("DROP FUNCTION IF EXISTS protect_test_case_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_test_sets_protect ON test_sets")
    op.execute("DROP FUNCTION IF EXISTS protect_test_set_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_test_cases_refresh_totals ON test_cases")
    op.execute("DROP FUNCTION IF EXISTS refresh_test_set_totals()")
    op.execute("ALTER TABLE submissions DROP CONSTRAINT IF EXISTS ck_submissions_test_set_mode")
    op.execute("ALTER TABLE submissions DROP CONSTRAINT IF EXISTS fk_submissions_test_set_problem")
    op.execute("DROP INDEX IF EXISTS idx_submissions_test_set")
    for column in ("memory_limit_mb_snapshot", "time_limit_ms_snapshot", "problem_version", "test_set_id"):
        op.execute(f"ALTER TABLE submissions DROP COLUMN IF EXISTS {column}")
    op.execute("ALTER TABLE test_cases ADD COLUMN problem_id BIGINT")
    op.execute("UPDATE test_cases tc SET problem_id = ts.problem_id FROM test_sets ts WHERE ts.id = tc.test_set_id")
    op.execute("ALTER TABLE test_cases ALTER COLUMN problem_id SET NOT NULL")
    op.execute("ALTER TABLE test_cases ADD CONSTRAINT test_cases_problem_id_fkey FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE test_cases ADD COLUMN is_sample BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE test_cases ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("ALTER TABLE test_cases DROP CONSTRAINT IF EXISTS uq_test_cases_set_sequence")
    op.execute("ALTER TABLE test_cases DROP COLUMN input_size_bytes")
    op.execute("ALTER TABLE test_cases DROP COLUMN output_size_bytes")
    op.execute("ALTER TABLE test_cases DROP COLUMN test_set_id")
    op.execute("ALTER TABLE test_cases ADD CONSTRAINT test_cases_problem_id_sequence_key UNIQUE (problem_id, sequence)")
    op.execute("CREATE INDEX idx_test_cases_problem ON test_cases (problem_id, sequence)")
    op.execute("DROP TABLE IF EXISTS test_sets")
    op.execute("ALTER TABLE problems DROP COLUMN version")
    op.execute("DROP TYPE IF EXISTS checker_type")
    op.execute("DROP TYPE IF EXISTS test_set_status")
