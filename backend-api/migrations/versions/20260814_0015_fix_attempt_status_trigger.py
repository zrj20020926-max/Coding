"""Fix the shared submission-attempt status transition trigger.

Revision ID: 20260814_0015
Revises: 20260813_0014
Create Date: 2026-08-14
"""

from collections.abc import Sequence
from typing import Optional, Union

from alembic import op

revision: str = "20260814_0015"
down_revision: Optional[str] = "20260813_0014"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    # NEW is a polymorphic record. Accessing a submissions-only field in a
    # combined boolean expression also evaluates it for submission_attempts.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_judge_status_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.status = OLD.status THEN
                RETURN NEW;
            END IF;
            IF TG_TABLE_NAME = 'submissions' THEN
                IF NEW.effective_attempt_id IS DISTINCT FROM OLD.effective_attempt_id
                   AND OLD.status IN ('Accepted', 'Wrong Answer', 'Compile Error',
                       'Runtime Error', 'Time Limit Exceeded', 'Memory Limit Exceeded',
                       'Output Limit Exceeded', 'System Error')
                   AND NEW.status IN ('Accepted', 'Wrong Answer', 'Compile Error',
                       'Runtime Error', 'Time Limit Exceeded', 'Memory Limit Exceeded',
                       'Output Limit Exceeded') THEN
                    RETURN NEW;
                END IF;
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


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_judge_status_transition()
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
