"""Add the ACM input/output learning course domain.

Revision ID: 20260814_0016
Revises: 20260814_0015
Create Date: 2026-08-14
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260814_0016"
down_revision: Optional[str] = "20260814_0015"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute("CREATE TYPE course_type AS ENUM ('input', 'output', 'mixed', 'performance')")
    op.execute(
        "CREATE TYPE exercise_progress_status AS ENUM ('not_started', 'attempted', 'completed')"
    )
    op.execute(
        """
        CREATE TABLE courses (
            id BIGSERIAL PRIMARY KEY,
            slug VARCHAR(100) NOT NULL UNIQUE,
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            type course_type NOT NULL,
            sort_order INTEGER NOT NULL CHECK (sort_order >= 0),
            is_public BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE chapters (
            id BIGSERIAL PRIMARY KEY,
            course_id BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            slug VARCHAR(100) NOT NULL UNIQUE,
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            sort_order INTEGER NOT NULL CHECK (sort_order >= 0),
            estimated_minutes INTEGER NOT NULL CHECK (estimated_minutes > 0),
            is_public BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_chapters_course_sort UNIQUE (course_id, sort_order)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE exercises (
            id BIGSERIAL PRIMARY KEY,
            problem_id BIGINT NOT NULL UNIQUE REFERENCES problems(id) ON DELETE RESTRICT,
            chapter_id BIGINT NOT NULL REFERENCES chapters(id) ON DELETE RESTRICT,
            sort_order INTEGER NOT NULL CHECK (sort_order >= 0),
            learning_objectives TEXT NOT NULL,
            v8_notes TEXT NOT NULL,
            nodejs_notes TEXT NOT NULL,
            common_mistakes JSONB NOT NULL DEFAULT '[]'::jsonb,
            starter_code_v8 TEXT NOT NULL,
            starter_code_nodejs TEXT NOT NULL,
            estimated_minutes INTEGER NOT NULL CHECK (estimated_minutes > 0),
            is_public BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_exercises_chapter_sort UNIQUE (chapter_id, sort_order)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE exercise_prerequisites (
            exercise_id BIGINT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
            prerequisite_id BIGINT NOT NULL REFERENCES exercises(id) ON DELETE RESTRICT,
            PRIMARY KEY (exercise_id, prerequisite_id),
            CONSTRAINT ck_exercise_prerequisites_not_self
                CHECK (exercise_id <> prerequisite_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE user_exercise_progress (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            exercise_id BIGINT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
            status exercise_progress_status NOT NULL DEFAULT 'not_started',
            selected_runtime VARCHAR(30) REFERENCES languages(slug) ON UPDATE CASCADE
                ON DELETE SET NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            v8_attempt_count INTEGER NOT NULL DEFAULT 0,
            nodejs_attempt_count INTEGER NOT NULL DEFAULT 0,
            v8_completed_at TIMESTAMPTZ,
            nodejs_completed_at TIMESTAMPTZ,
            first_completed_at TIMESTAMPTZ,
            last_attempted_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, exercise_id),
            CONSTRAINT ck_exercise_progress_runtime_attempt_counts CHECK (
                v8_attempt_count >= 0 AND nodejs_attempt_count >= 0
            ),
            CONSTRAINT ck_exercise_progress_selected_runtime CHECK (
                selected_runtime IS NULL
                OR selected_runtime IN ('javascript-v8', 'nodejs')
            )
        )
        """
    )

    op.execute("CREATE INDEX idx_courses_public_sort ON courses (sort_order, id) WHERE is_public")
    op.execute(
        "CREATE INDEX idx_chapters_public_course_sort "
        "ON chapters (course_id, sort_order, id) WHERE is_public"
    )
    op.execute(
        "CREATE INDEX idx_exercises_public_chapter_sort "
        "ON exercises (chapter_id, sort_order, id) WHERE is_public"
    )
    op.execute(
        "CREATE INDEX idx_exercise_prerequisites_prerequisite "
        "ON exercise_prerequisites (prerequisite_id)"
    )
    op.execute(
        "CREATE INDEX idx_user_exercise_progress_user_status "
        "ON user_exercise_progress (user_id, status, exercise_id)"
    )

    op.execute(
        """
        CREATE FUNCTION reject_exercise_prerequisite_cycle()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Serialize prerequisite graph edits so two concurrent reciprocal
            -- inserts cannot both pass against an incomplete MVCC snapshot.
            PERFORM pg_advisory_xact_lock(hashtext('codearena:exercise-prerequisites'));
            IF EXISTS (
                WITH RECURSIVE dependencies(id) AS (
                    SELECT prerequisite_id
                      FROM exercise_prerequisites
                     WHERE exercise_id = NEW.exercise_id
                    UNION
                    SELECT relation.prerequisite_id
                      FROM exercise_prerequisites relation
                      JOIN dependencies ON relation.exercise_id = dependencies.id
                )
                SELECT 1 FROM dependencies WHERE id = NEW.exercise_id
            ) THEN
                RAISE EXCEPTION 'exercise prerequisite cycle detected'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_exercise_prerequisite_acyclic "
        "AFTER INSERT OR UPDATE ON exercise_prerequisites "
        "DEFERRABLE INITIALLY IMMEDIATE FOR EACH ROW "
        "EXECUTE FUNCTION reject_exercise_prerequisite_cycle()"
    )
    for table, trigger in (
        ("courses", "trg_courses_updated_at"),
        ("chapters", "trg_chapters_updated_at"),
        ("exercises", "trg_exercises_updated_at"),
        ("user_exercise_progress", "trg_user_exercise_progress_updated_at"),
    ):
        op.execute(
            f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_user_exercise_progress_updated_at ON user_exercise_progress"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_exercises_updated_at ON exercises")
    op.execute("DROP TRIGGER IF EXISTS trg_chapters_updated_at ON chapters")
    op.execute("DROP TRIGGER IF EXISTS trg_courses_updated_at ON courses")
    op.execute("DROP TRIGGER IF EXISTS trg_exercise_prerequisite_acyclic ON exercise_prerequisites")
    op.execute("DROP FUNCTION IF EXISTS reject_exercise_prerequisite_cycle()")
    op.execute("DROP TABLE user_exercise_progress")
    op.execute("DROP TABLE exercise_prerequisites")
    op.execute("DROP TABLE exercises")
    op.execute("DROP TABLE chapters")
    op.execute("DROP TABLE courses")
    op.execute("DROP TYPE exercise_progress_status")
    op.execute("DROP TYPE course_type")
