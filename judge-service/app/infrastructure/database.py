import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.domain.models import (
    CheckerType,
    JudgeResult,
    SubmissionJob,
    SubmissionMode,
    SubmissionStatus,
    TestCase,
)
from app.errors import InfrastructureError


class JudgeRepository:
    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(database_url, pool_pre_ping=True)

    async def close(self) -> None:
        await self.engine.dispose()

    async def load_submission(self, submission_id: UUID) -> SubmissionJob | None:
        statement = text(
            """
            SELECT s.id, s.problem_id, l.slug AS language, s.status::text AS status,
                   s.mode::text AS mode,
                   s.source_object_key, s.source_checksum,
                   s.test_set_id, s.problem_version,
                   s.time_limit_ms_snapshot, s.memory_limit_mb_snapshot,
                   COALESCE(ts.checker_type::text, 'exact') AS checker_type,
                   ts.absolute_tolerance, ts.relative_tolerance
              FROM submissions s
              JOIN languages l ON l.id = s.language_id
              LEFT JOIN test_sets ts ON ts.id = s.test_set_id
             WHERE s.id = :submission_id
            """
        )
        try:
            async with self.engine.connect() as connection:
                result = await connection.execute(
                    statement, {"submission_id": submission_id}
                )
                row = result.mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL submission lookup failed") from exc
        if row is None or not row["source_object_key"]:
            return None
        return SubmissionJob(
            id=row["id"],
            problem_id=row["problem_id"],
            language=row["language"],
            status=SubmissionStatus(row["status"]),
            mode=SubmissionMode(row["mode"]),
            test_set_id=row["test_set_id"],
            problem_version=row["problem_version"],
            source_object_key=row["source_object_key"],
            source_checksum=row["source_checksum"],
            time_limit_ms=row["time_limit_ms_snapshot"],
            memory_limit_mb=row["memory_limit_mb_snapshot"],
            checker_type=CheckerType(row["checker_type"]),
            absolute_tolerance=(
                Decimal(row["absolute_tolerance"])
                if row["absolute_tolerance"] is not None
                else None
            ),
            relative_tolerance=(
                Decimal(row["relative_tolerance"])
                if row["relative_tolerance"] is not None
                else None
            ),
        )

    async def load_test_cases(self, job: SubmissionJob) -> list[TestCase]:
        if job.mode is SubmissionMode.SAMPLE:
            return await self._load_sample_case(job.problem_id)
        if job.test_set_id is None:
            return []
        return await self._load_hidden_test_cases(job.test_set_id)

    async def _load_sample_case(self, problem_id: int) -> list[TestCase]:
        statement = text(
            "SELECT sample_input, sample_output FROM problems WHERE id = :problem_id"
        )
        try:
            async with self.engine.connect() as connection:
                row = (
                    await connection.execute(statement, {"problem_id": problem_id})
                ).mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL sample-case lookup failed") from exc
        if row is None:
            return []
        stdin = row["sample_input"].encode("utf-8")
        expected = row["sample_output"].encode("utf-8")
        return [
            TestCase(
                id=uuid5(NAMESPACE_URL, f"codearena:problem:{problem_id}:sample"),
                input_object_key=None,
                output_object_key=None,
                checksum=hashlib.sha256(stdin + b"\0" + expected).hexdigest(),
                score=Decimal("100"),
                sequence=0,
                inline_input=stdin,
                inline_output=expected,
            )
        ]

    async def _load_hidden_test_cases(self, test_set_id: UUID) -> list[TestCase]:
        statement = text(
            """
            SELECT id, input_object_key, output_object_key, checksum, score, sequence
             FROM test_cases
             WHERE test_set_id = :test_set_id
             ORDER BY sequence
            """
        )
        try:
            async with self.engine.connect() as connection:
                result = await connection.execute(statement, {"test_set_id": test_set_id})
                rows = result.mappings().all()
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL test-case lookup failed") from exc
        return [
            TestCase(
                id=row["id"],
                input_object_key=row["input_object_key"],
                output_object_key=row["output_object_key"],
                checksum=row["checksum"],
                score=Decimal(row["score"]),
                sequence=row["sequence"],
            )
            for row in rows
        ]

    async def transition(
        self,
        submission_id: UUID,
        expected: SubmissionStatus,
        next_status: SubmissionStatus,
    ) -> bool:
        statement = text(
            """
            UPDATE submissions
               SET status = CAST(:next_status AS submission_status)
             WHERE id = :submission_id
               AND status = CAST(:expected_status AS submission_status)
            RETURNING id
            """
        )
        try:
            async with self.engine.begin() as connection:
                updated = await connection.scalar(
                    statement,
                    {
                        "submission_id": submission_id,
                        "expected_status": expected.value,
                        "next_status": next_status.value,
                    },
                )
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL status transition failed") from exc
        return updated is not None

    async def finalize(
        self,
        submission_id: UUID,
        expected: SubmissionStatus,
        result: JudgeResult,
    ) -> bool:
        passed = sum(
            item.status is SubmissionStatus.ACCEPTED for item in result.case_results
        )
        score = sum(
            (
                item.score
                for item in result.case_results
                if item.status is SubmissionStatus.ACCEPTED
            ),
            Decimal("0"),
        )
        judged_at = datetime.now(UTC)
        update = text(
            """
            UPDATE submissions
               SET status = CAST(:next_status AS submission_status),
                   compiler_output = :compiler_output,
                   error_message = :error_message,
                   sample_output = :sample_output,
                   time_used_ms = :time_used_ms,
                   memory_used_kb = :memory_used_kb,
                   passed_case_count = :passed_case_count,
                   total_case_count = :total_case_count,
                   score = :score,
                   judged_at = :judged_at
             WHERE id = :submission_id
               AND status = CAST(:expected_status AS submission_status)
            RETURNING id, user_id, problem_id, mode::text AS mode, is_rejudge
            """
        )
        update_progress = text(
            """
            INSERT INTO user_problem_progress (
                user_id, problem_id, attempt_count, accepted,
                first_accepted_at, last_submission_id, updated_at
            ) VALUES (
                :user_id, :problem_id, 1, :accepted,
                CASE WHEN :accepted THEN CAST(:judged_at AS TIMESTAMPTZ) ELSE NULL END,
                :submission_id, CAST(:judged_at AS TIMESTAMPTZ)
            )
            ON CONFLICT (user_id, problem_id) DO UPDATE SET
                attempt_count = user_problem_progress.attempt_count + 1,
                accepted = user_problem_progress.accepted OR EXCLUDED.accepted,
                first_accepted_at = COALESCE(
                    user_problem_progress.first_accepted_at,
                    EXCLUDED.first_accepted_at
                ),
                last_submission_id = EXCLUDED.last_submission_id,
                updated_at = EXCLUDED.updated_at
            RETURNING (
                :accepted AND first_accepted_at = CAST(:judged_at AS TIMESTAMPTZ)
            ) AS first_accepted
            """
        )
        insert_stat_event = text(
            """
            INSERT INTO submission_stat_events (
                submission_id, user_id, problem_id, terminal_status, accepted, applied_at
            ) VALUES (
                :submission_id, :user_id, :problem_id,
                CAST(:terminal_status AS submission_status), :accepted,
                CAST(:judged_at AS TIMESTAMPTZ)
            )
            ON CONFLICT (submission_id) DO NOTHING
            RETURNING submission_id
            """
        )
        update_user_stats = text(
            """
            UPDATE users
               SET submission_count = submission_count + 1,
                   accepted_count = accepted_count + :accepted_increment,
                   solved_count = solved_count + :solved_increment
             WHERE id = :user_id
            """
        )
        update_problem_stats = text(
            """
            UPDATE problems
               SET submission_count = submission_count + 1,
                   accepted_count = accepted_count + :accepted_increment
             WHERE id = :problem_id
            """
        )
        insert_case = text(
            """
            INSERT INTO submission_case_results (
                submission_id, test_case_id, status, time_used_ms,
                memory_used_kb, exit_code, stdout_excerpt, stderr_excerpt
            ) VALUES (
                :submission_id, :test_case_id, CAST(:status AS submission_status),
                :time_used_ms, :memory_used_kb, :exit_code, NULL, NULL
            )
            """
        )
        try:
            async with self.engine.begin() as connection:
                # Finalizers share this transaction lock with each other. The statistics
                # rebuild command takes the exclusive variant, so it cannot race live judges.
                await connection.execute(
                    text(
                        "SELECT pg_advisory_xact_lock_shared("
                        "hashtext('codearena:training-statistics'))"
                    )
                )
                updated = (
                    await connection.execute(
                        update,
                        {
                            "submission_id": submission_id,
                            "expected_status": expected.value,
                            "next_status": result.status.value,
                            "compiler_output": (result.compiler_output or "")[:16_384]
                            or None,
                            "error_message": (result.error_message or "")[:2_000]
                            or None,
                            "sample_output": (result.public_output or "")[:16_384]
                            or None,
                            "time_used_ms": result.time_used_ms,
                            "memory_used_kb": result.memory_used_kb,
                            "passed_case_count": passed,
                            "total_case_count": result.total_case_count,
                            "score": score,
                            "judged_at": judged_at,
                        },
                    )
                ).mappings().one_or_none()
                if updated is None:
                    return False
                await connection.execute(
                    text("DELETE FROM submission_case_results WHERE submission_id = :id"),
                    {"id": submission_id},
                )
                if updated["mode"] == SubmissionMode.JUDGE.value and result.case_results:
                    await connection.execute(
                        insert_case,
                        [
                            {
                                "submission_id": submission_id,
                                "test_case_id": item.test_case_id,
                                "status": item.status.value,
                                "time_used_ms": item.time_used_ms,
                                "memory_used_kb": item.memory_used_kb,
                                "exit_code": item.exit_code,
                            }
                            for item in result.case_results
                        ],
                    )
                if (
                    updated["mode"] == SubmissionMode.JUDGE.value
                    and not updated["is_rejudge"]
                ):
                    accepted = result.status is SubmissionStatus.ACCEPTED
                    stat_event_id = await connection.scalar(
                        insert_stat_event,
                        {
                            "submission_id": submission_id,
                            "user_id": updated["user_id"],
                            "problem_id": updated["problem_id"],
                            "terminal_status": result.status.value,
                            "accepted": accepted,
                            "judged_at": judged_at,
                        },
                    )
                    if stat_event_id is None:
                        return True
                    first_accepted = bool(
                        await connection.scalar(
                            update_progress,
                            {
                                "user_id": updated["user_id"],
                                "problem_id": updated["problem_id"],
                                "submission_id": submission_id,
                                "accepted": accepted,
                                "judged_at": judged_at,
                            },
                        )
                    )
                    counters = {
                        "user_id": updated["user_id"],
                        "problem_id": updated["problem_id"],
                        "accepted_increment": int(accepted),
                        "solved_increment": int(first_accepted),
                    }
                    await connection.execute(update_user_stats, counters)
                    await connection.execute(update_problem_stats, counters)
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL result finalization failed") from exc
        return True


def create_repository(database_url: str) -> JudgeRepository:
    return JudgeRepository(database_url)
