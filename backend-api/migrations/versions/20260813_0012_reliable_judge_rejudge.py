"""Add reliable judge attempts, test groups, OLE and resumable rejudge tasks.

Revision ID: 20260813_0012
Revises: 20260812_0011
Create Date: 2026-08-13
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260813_0012"
down_revision: Optional[str] = "20260812_0011"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    # PostgreSQL does not allow a newly-added enum value to be used by later statements
    # in the same transaction, so add it in an explicit autocommit block.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE submission_status ADD VALUE IF NOT EXISTS "
            "'Output Limit Exceeded' BEFORE 'System Error'"
        )

    op.execute(
        """
        CREATE TABLE test_groups (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            test_set_id UUID NOT NULL REFERENCES test_sets(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            sequence INTEGER NOT NULL CHECK (sequence >= 0),
            score NUMERIC(9, 2) NOT NULL CHECK (score > 0),
            short_circuit BOOLEAN NOT NULL DEFAULT TRUE,
            dependency_group_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_test_groups_set_sequence UNIQUE (test_set_id, sequence),
            CONSTRAINT uq_test_groups_id_set UNIQUE (id, test_set_id),
            CONSTRAINT fk_test_groups_dependency
                FOREIGN KEY (dependency_group_id, test_set_id)
                REFERENCES test_groups(id, test_set_id) ON DELETE RESTRICT,
            CONSTRAINT ck_test_groups_no_self_dependency
                CHECK (dependency_group_id IS NULL OR dependency_group_id <> id)
        )
        """
    )
    # Preserve legacy per-case scoring by creating one deterministic group per case.
    op.execute(
        """
        INSERT INTO test_groups (id, test_set_id, name, sequence, score, short_circuit)
        SELECT gen_random_uuid(), tc.test_set_id, 'case-' || tc.sequence,
               tc.sequence, tc.score, TRUE
          FROM test_cases tc
        """
    )
    op.execute("ALTER TABLE test_cases ADD COLUMN group_id UUID")
    op.execute(
        """
        UPDATE test_cases tc
           SET group_id = tg.id
          FROM test_groups tg
         WHERE tg.test_set_id = tc.test_set_id AND tg.sequence = tc.sequence
        """
    )
    op.execute("ALTER TABLE test_cases ALTER COLUMN group_id SET NOT NULL")
    op.execute(
        "ALTER TABLE test_cases ADD CONSTRAINT fk_test_cases_group_set "
        "FOREIGN KEY (group_id, test_set_id) REFERENCES test_groups(id, test_set_id) "
        "ON DELETE RESTRICT"
    )
    op.execute("CREATE INDEX idx_test_cases_group_sequence ON test_cases (group_id, sequence)")
    op.execute("DROP TRIGGER IF EXISTS trg_test_cases_refresh_totals ON test_cases")
    op.execute("DROP FUNCTION IF EXISTS refresh_test_set_totals()")
    op.execute(
        """
        CREATE FUNCTION refresh_test_set_totals()
        RETURNS TRIGGER AS $$
        DECLARE target_id UUID;
        BEGIN
            target_id := COALESCE(NEW.test_set_id, OLD.test_set_id);
            UPDATE test_sets SET
                case_count = (SELECT count(*) FROM test_cases WHERE test_set_id=target_id),
                total_score = COALESCE((SELECT sum(score) FROM test_groups
                                        WHERE test_set_id=target_id), 0)
            WHERE id=target_id;
            IF TG_OP='UPDATE' AND OLD.test_set_id <> NEW.test_set_id THEN
                UPDATE test_sets SET
                    case_count=(SELECT count(*) FROM test_cases
                                WHERE test_set_id=OLD.test_set_id),
                    total_score=COALESCE((SELECT sum(score) FROM test_groups
                                         WHERE test_set_id=OLD.test_set_id),0)
                WHERE id=OLD.test_set_id;
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_test_cases_refresh_totals AFTER INSERT OR UPDATE OR DELETE "
        "ON test_cases FOR EACH ROW EXECUTE FUNCTION refresh_test_set_totals()"
    )
    op.execute(
        "CREATE TRIGGER trg_test_groups_refresh_totals AFTER INSERT OR UPDATE OR DELETE "
        "ON test_groups FOR EACH ROW EXECUTE FUNCTION refresh_test_set_totals()"
    )

    op.execute(
        """
        CREATE TABLE submission_attempts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            submission_id UUID NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
            sequence INTEGER NOT NULL CHECK (sequence > 0),
            kind VARCHAR(20) NOT NULL CHECK (kind IN ('initial', 'rejudge')),
            status submission_status NOT NULL DEFAULT 'Pending',
            problem_id BIGINT NOT NULL REFERENCES problems(id) ON DELETE RESTRICT,
            test_set_id UUID REFERENCES test_sets(id) ON DELETE RESTRICT,
            problem_version INTEGER NOT NULL CHECK (problem_version > 0),
            time_limit_ms_snapshot INTEGER NOT NULL CHECK (time_limit_ms_snapshot > 0),
            memory_limit_mb_snapshot INTEGER NOT NULL CHECK (memory_limit_mb_snapshot > 0),
            compiler_output TEXT,
            error_message TEXT,
            public_output TEXT,
            time_used_ms INTEGER CHECK (time_used_ms >= 0),
            memory_used_kb INTEGER CHECK (memory_used_kb >= 0),
            passed_case_count INTEGER NOT NULL DEFAULT 0 CHECK (passed_case_count >= 0),
            total_case_count INTEGER NOT NULL DEFAULT 0 CHECK (total_case_count >= 0),
            score NUMERIC(9, 2) NOT NULL DEFAULT 0 CHECK (score >= 0),
            lease_owner VARCHAR(128),
            lease_expires_at TIMESTAMPTZ,
            started_at TIMESTAMPTZ,
            judged_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_submission_attempt_sequence UNIQUE (submission_id, sequence),
            CONSTRAINT fk_attempt_test_set_problem FOREIGN KEY (test_set_id, problem_id)
                REFERENCES test_sets(id, problem_id) ON DELETE RESTRICT,
            CONSTRAINT ck_attempt_test_set_kind CHECK (
                test_set_id IS NOT NULL OR kind = 'initial'
            )
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_submission_initial_attempt ON submission_attempts "
        "(submission_id) WHERE kind = 'initial'"
    )
    op.execute(
        "CREATE INDEX idx_submission_attempts_lease ON submission_attempts "
        "(status, lease_expires_at) WHERE status IN ('Pending', 'Compiling', 'Running')"
    )
    op.execute("ALTER TABLE submissions ADD COLUMN effective_attempt_id UUID")
    op.execute(
        """
        INSERT INTO submission_attempts (
            id, submission_id, sequence, kind, status, problem_id, test_set_id,
            problem_version, time_limit_ms_snapshot, memory_limit_mb_snapshot,
            compiler_output, error_message, public_output, time_used_ms,
            memory_used_kb, passed_case_count, total_case_count, score,
            started_at, judged_at, created_at, updated_at
        )
        SELECT gen_random_uuid(), s.id, 1, 'initial', s.status, s.problem_id, s.test_set_id,
               s.problem_version, s.time_limit_ms_snapshot, s.memory_limit_mb_snapshot,
               s.compiler_output, s.error_message, s.sample_output, s.time_used_ms,
               s.memory_used_kb, s.passed_case_count, s.total_case_count, s.score,
               CASE WHEN s.status <> 'Pending' THEN s.updated_at ELSE NULL END,
               s.judged_at, s.created_at, s.updated_at
          FROM submissions s
        """
    )
    op.execute(
        "UPDATE submissions s SET effective_attempt_id = sa.id "
        "FROM submission_attempts sa WHERE sa.submission_id = s.id AND sa.kind = 'initial'"
    )
    op.execute(
        "ALTER TABLE submissions ADD CONSTRAINT fk_submissions_effective_attempt "
        "FOREIGN KEY (effective_attempt_id) REFERENCES submission_attempts(id) ON DELETE RESTRICT "
        "DEFERRABLE INITIALLY DEFERRED"
    )
    op.execute(
        """
        CREATE TABLE submission_attempt_case_results (
            id BIGSERIAL PRIMARY KEY,
            attempt_id UUID NOT NULL REFERENCES submission_attempts(id) ON DELETE CASCADE,
            test_case_id UUID NOT NULL REFERENCES test_cases(id) ON DELETE RESTRICT,
            group_id UUID NOT NULL REFERENCES test_groups(id) ON DELETE RESTRICT,
            status submission_status NOT NULL,
            time_used_ms INTEGER CHECK (time_used_ms >= 0),
            memory_used_kb INTEGER CHECK (memory_used_kb >= 0),
            exit_code INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_attempt_case_result UNIQUE (attempt_id, test_case_id)
        )
        """
    )
    op.execute(
        """
        INSERT INTO submission_attempt_case_results (
            attempt_id, test_case_id, group_id, status, time_used_ms,
            memory_used_kb, exit_code, created_at
        )
        SELECT sa.id, scr.test_case_id, tc.group_id, scr.status, scr.time_used_ms,
               scr.memory_used_kb, scr.exit_code, scr.created_at
          FROM submission_case_results scr
          JOIN submission_attempts sa
            ON sa.submission_id = scr.submission_id AND sa.kind = 'initial'
          JOIN test_cases tc ON tc.id = scr.test_case_id
        """
    )
    op.execute(
        """
        CREATE TABLE submission_attempt_group_results (
            id BIGSERIAL PRIMARY KEY,
            attempt_id UUID NOT NULL REFERENCES submission_attempts(id) ON DELETE CASCADE,
            group_id UUID NOT NULL REFERENCES test_groups(id) ON DELETE RESTRICT,
            status submission_status NOT NULL,
            score NUMERIC(9, 2) NOT NULL DEFAULT 0 CHECK (score >= 0),
            passed_case_count INTEGER NOT NULL DEFAULT 0 CHECK (passed_case_count >= 0),
            total_case_count INTEGER NOT NULL DEFAULT 0 CHECK (total_case_count >= 0),
            skipped BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_attempt_group_result UNIQUE (attempt_id, group_id)
        )
        """
    )

    op.execute("ALTER TABLE rejudge_tasks ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'queued'")
    op.execute("ALTER TABLE rejudge_tasks ADD COLUMN paused_at TIMESTAMPTZ")
    op.execute("ALTER TABLE rejudge_tasks ADD COLUMN completed_at TIMESTAMPTZ")
    op.execute(
        "ALTER TABLE rejudge_tasks ADD CONSTRAINT ck_rejudge_task_status CHECK "
        "(status IN ('queued', 'running', 'paused', 'completed', 'completed_with_errors'))"
    )
    op.execute("ALTER TABLE rejudge_task_items ADD COLUMN attempt_id UUID")
    op.execute(
        "ALTER TABLE rejudge_task_items ADD CONSTRAINT fk_rejudge_item_attempt "
        "FOREIGN KEY (attempt_id) REFERENCES submission_attempts(id) ON DELETE RESTRICT"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_rejudge_item_attempt ON rejudge_task_items (attempt_id) "
        "WHERE attempt_id IS NOT NULL"
    )
    op.execute("ALTER TABLE rejudge_task_items ALTER COLUMN rejudge_submission_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE rejudge_task_items ADD CONSTRAINT ck_rejudge_item_execution CHECK "
        "((attempt_id IS NOT NULL) <> (rejudge_submission_id IS NOT NULL))"
    )

    op.execute("DROP TRIGGER IF EXISTS trg_submissions_status_transition ON submissions")
    op.execute("DROP FUNCTION IF EXISTS enforce_submission_status_transition()")
    op.execute(
        """
        CREATE FUNCTION enforce_judge_status_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.status = OLD.status THEN RETURN NEW; END IF;
            IF TG_TABLE_NAME = 'submissions'
               AND NEW.effective_attempt_id IS DISTINCT FROM OLD.effective_attempt_id
               AND OLD.status IN ('Accepted', 'Wrong Answer', 'Compile Error',
                   'Runtime Error', 'Time Limit Exceeded', 'Memory Limit Exceeded',
                   'Output Limit Exceeded', 'System Error')
               AND NEW.status IN ('Accepted', 'Wrong Answer', 'Compile Error',
                   'Runtime Error', 'Time Limit Exceeded', 'Memory Limit Exceeded',
                   'Output Limit Exceeded') THEN
                RETURN NEW;
            END IF;
            IF (OLD.status = 'Pending' AND NEW.status = 'Compiling')
               OR (OLD.status = 'Compiling' AND NEW.status IN (
                    'Running', 'Compile Error', 'System Error'))
               OR (OLD.status = 'Running' AND NEW.status IN (
                    'Accepted', 'Wrong Answer', 'Runtime Error', 'Time Limit Exceeded',
                    'Memory Limit Exceeded', 'Output Limit Exceeded', 'System Error')) THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'invalid judge status transition: % -> %', OLD.status, NEW.status
                USING ERRCODE = '23514';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_submissions_status_transition BEFORE UPDATE OF status ON submissions "
        "FOR EACH ROW EXECUTE FUNCTION enforce_judge_status_transition()"
    )
    op.execute(
        "CREATE TRIGGER trg_attempts_status_transition BEFORE UPDATE OF status "
        "ON submission_attempts "
        "FOR EACH ROW EXECUTE FUNCTION enforce_judge_status_transition()"
    )
    op.execute(
        "ALTER TABLE submission_stat_events DROP CONSTRAINT IF EXISTS "
        "ck_stat_event_terminal_status"
    )
    op.execute(
        "ALTER TABLE submission_stat_events ADD CONSTRAINT ck_stat_event_terminal_status "
        "CHECK (terminal_status IN ('Accepted', 'Wrong Answer', 'Compile Error', "
        "'Runtime Error', 'Time Limit Exceeded', 'Memory Limit Exceeded', "
        "'Output Limit Exceeded'))"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_test_cases_protect ON test_cases")
    op.execute("DROP FUNCTION IF EXISTS protect_test_case_mutation()")
    op.execute(
        """
        CREATE FUNCTION protect_test_case_mutation()
        RETURNS TRIGGER AS $$
        DECLARE target_id UUID; target_status test_set_status;
        BEGIN
            target_id := COALESCE(OLD.test_set_id, NEW.test_set_id);
            SELECT status INTO target_status FROM test_sets WHERE id = target_id;
            IF EXISTS (SELECT 1 FROM submissions WHERE test_set_id = target_id)
               OR EXISTS (SELECT 1 FROM submission_attempts WHERE test_set_id = target_id) THEN
                RAISE EXCEPTION 'cases in a referenced test set are immutable'
                    USING ERRCODE = '23514';
            END IF;
            IF target_status NOT IN ('draft', 'invalid') THEN
                RAISE EXCEPTION 'cases can only change in draft or invalid test sets'
                    USING ERRCODE = '23514';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_test_cases_protect BEFORE INSERT OR UPDATE OR DELETE ON test_cases "
        "FOR EACH ROW EXECUTE FUNCTION protect_test_case_mutation()"
    )
    op.execute(
        """
        CREATE FUNCTION protect_attempt_snapshot()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.submission_id <> OLD.submission_id OR NEW.sequence <> OLD.sequence
               OR NEW.kind <> OLD.kind OR NEW.problem_id <> OLD.problem_id
               OR NEW.test_set_id IS DISTINCT FROM OLD.test_set_id
               OR NEW.problem_version <> OLD.problem_version
               OR NEW.time_limit_ms_snapshot <> OLD.time_limit_ms_snapshot
               OR NEW.memory_limit_mb_snapshot <> OLD.memory_limit_mb_snapshot THEN
                RAISE EXCEPTION 'judge attempt snapshot is immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_attempt_snapshot_immutable BEFORE UPDATE ON submission_attempts "
        "FOR EACH ROW EXECUTE FUNCTION protect_attempt_snapshot()"
    )
    op.execute(
        """
        CREATE FUNCTION protect_test_group_mutation()
        RETURNS TRIGGER AS $$
        DECLARE target_id UUID; target_status test_set_status;
        BEGIN
            target_id := COALESCE(OLD.test_set_id, NEW.test_set_id);
            SELECT status INTO target_status FROM test_sets WHERE id = target_id;
            IF EXISTS (SELECT 1 FROM submissions WHERE test_set_id = target_id)
               OR EXISTS (SELECT 1 FROM submission_attempts WHERE test_set_id = target_id) THEN
                RAISE EXCEPTION 'groups in a referenced test set are immutable'
                    USING ERRCODE = '23514';
            END IF;
            IF target_status NOT IN ('draft', 'invalid') THEN
                RAISE EXCEPTION 'groups can only change in draft or invalid test sets'
                    USING ERRCODE = '23514';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_test_groups_protect BEFORE INSERT OR UPDATE OR DELETE ON test_groups "
        "FOR EACH ROW EXECUTE FUNCTION protect_test_group_mutation()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_test_groups_refresh_totals ON test_groups")
    op.execute("DROP TRIGGER IF EXISTS trg_test_groups_protect ON test_groups")
    op.execute("DROP FUNCTION IF EXISTS protect_test_group_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_attempt_snapshot_immutable ON submission_attempts")
    op.execute("DROP FUNCTION IF EXISTS protect_attempt_snapshot()")
    op.execute("DROP TRIGGER IF EXISTS trg_attempts_status_transition ON submission_attempts")
    op.execute("DROP TRIGGER IF EXISTS trg_submissions_status_transition ON submissions")
    op.execute("DROP FUNCTION IF EXISTS enforce_judge_status_transition()")
    op.execute(
        "ALTER TABLE submission_stat_events DROP CONSTRAINT IF EXISTS "
        "ck_stat_event_terminal_status"
    )
    op.execute(
        "ALTER TABLE submission_stat_events ADD CONSTRAINT ck_stat_event_terminal_status "
        "CHECK (terminal_status IN ('Accepted', 'Wrong Answer', 'Compile Error', "
        "'Runtime Error', 'Time Limit Exceeded', 'Memory Limit Exceeded', 'System Error'))"
    )
    op.execute("DROP INDEX IF EXISTS uq_rejudge_item_attempt")
    op.execute("ALTER TABLE rejudge_task_items DROP CONSTRAINT IF EXISTS ck_rejudge_item_execution")
    op.execute("ALTER TABLE rejudge_task_items DROP CONSTRAINT IF EXISTS fk_rejudge_item_attempt")
    op.execute("ALTER TABLE rejudge_task_items DROP COLUMN IF EXISTS attempt_id")
    op.execute("ALTER TABLE rejudge_task_items ALTER COLUMN rejudge_submission_id SET NOT NULL")
    op.execute("ALTER TABLE rejudge_tasks DROP CONSTRAINT IF EXISTS ck_rejudge_task_status")
    for column in ("completed_at", "paused_at", "status"):
        op.execute(f"ALTER TABLE rejudge_tasks DROP COLUMN IF EXISTS {column}")
    op.execute("DROP TABLE IF EXISTS submission_attempt_group_results")
    op.execute("DROP TABLE IF EXISTS submission_attempt_case_results")
    op.execute("ALTER TABLE submissions DROP CONSTRAINT IF EXISTS fk_submissions_effective_attempt")
    op.execute("ALTER TABLE submissions DROP COLUMN IF EXISTS effective_attempt_id")
    op.execute("DROP TABLE IF EXISTS submission_attempts")
    op.execute("ALTER TABLE test_cases DROP CONSTRAINT IF EXISTS fk_test_cases_group_set")
    op.execute("DROP INDEX IF EXISTS idx_test_cases_group_sequence")
    op.execute("ALTER TABLE test_cases DROP COLUMN IF EXISTS group_id")
    op.execute("DROP TABLE IF EXISTS test_groups")
    op.execute("DROP TRIGGER IF EXISTS trg_test_cases_refresh_totals ON test_cases")
    op.execute("DROP FUNCTION IF EXISTS refresh_test_set_totals()")
    op.execute(
        """
        CREATE FUNCTION refresh_test_set_totals()
        RETURNS TRIGGER AS $$
        DECLARE target_id UUID;
        BEGIN
            target_id := COALESCE(NEW.test_set_id, OLD.test_set_id);
            UPDATE test_sets SET
                case_count=(SELECT count(*) FROM test_cases WHERE test_set_id=target_id),
                total_score=COALESCE((SELECT sum(score) FROM test_cases
                                      WHERE test_set_id=target_id),0)
            WHERE id=target_id;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_test_cases_refresh_totals AFTER INSERT OR UPDATE OR DELETE "
        "ON test_cases FOR EACH ROW EXECUTE FUNCTION refresh_test_set_totals()"
    )
    op.execute(
        """
        CREATE FUNCTION enforce_submission_status_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.status = OLD.status THEN RETURN NEW; END IF;
            IF (OLD.status = 'Pending' AND NEW.status = 'Compiling')
               OR (OLD.status = 'Compiling' AND NEW.status IN (
                   'Running', 'Compile Error', 'System Error'))
               OR (OLD.status = 'Running' AND NEW.status IN ('Accepted', 'Wrong Answer',
                   'Runtime Error', 'Time Limit Exceeded', 'Memory Limit Exceeded', 'System Error'))
            THEN RETURN NEW; END IF;
            RAISE EXCEPTION 'invalid submission status transition: % -> %', OLD.status, NEW.status
                USING ERRCODE = '23514';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_submissions_status_transition BEFORE UPDATE OF status ON submissions "
        "FOR EACH ROW EXECUTE FUNCTION enforce_submission_status_transition()"
    )
    # PostgreSQL enum values intentionally remain on downgrade.
