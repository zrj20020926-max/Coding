from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine

from app.domain.models import (
    JudgeResult,
    SubmissionJob,
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
                   s.source_object_key, s.source_checksum,
                   p.time_limit_ms, p.memory_limit_mb
              FROM submissions s
              JOIN problems p ON p.id = s.problem_id
              JOIN languages l ON l.id = s.language_id
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
            source_object_key=row["source_object_key"],
            source_checksum=row["source_checksum"],
            time_limit_ms=row["time_limit_ms"],
            memory_limit_mb=row["memory_limit_mb"],
        )

    async def load_test_cases(self, problem_id: int) -> list[TestCase]:
        statement = text(
            """
            SELECT id, input_object_key, output_object_key, checksum, score, sequence
              FROM test_cases
             WHERE problem_id = :problem_id AND is_hidden = TRUE
             ORDER BY sequence
            """
        )
        try:
            async with self.engine.connect() as connection:
                result = await connection.execute(statement, {"problem_id": problem_id})
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
        update = text(
            """
            UPDATE submissions
               SET status = CAST(:next_status AS submission_status),
                   compiler_output = :compiler_output,
                   error_message = :error_message,
                   time_used_ms = :time_used_ms,
                   memory_used_kb = :memory_used_kb,
                   passed_case_count = :passed_case_count,
                   total_case_count = :total_case_count,
                   score = :score,
                   judged_at = now()
             WHERE id = :submission_id
               AND status = CAST(:expected_status AS submission_status)
            RETURNING id
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
                updated = await connection.scalar(
                    update,
                    {
                        "submission_id": submission_id,
                        "expected_status": expected.value,
                        "next_status": result.status.value,
                        "compiler_output": (result.compiler_output or "")[:16_384] or None,
                        "error_message": (result.error_message or "")[:2_000] or None,
                        "time_used_ms": result.time_used_ms,
                        "memory_used_kb": result.memory_used_kb,
                        "passed_case_count": passed,
                        "total_case_count": result.total_case_count,
                        "score": score,
                    },
                )
                if updated is None:
                    return False
                await connection.execute(
                    text("DELETE FROM submission_case_results WHERE submission_id = :id"),
                    {"id": submission_id},
                )
                if result.case_results:
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
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL result finalization failed") from exc
        return True


def create_repository(database_url: str) -> JudgeRepository:
    return JudgeRepository(database_url)
