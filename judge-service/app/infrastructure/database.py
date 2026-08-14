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

    async def claim_submission(
        self,
        submission_id: UUID,
        attempt_id: UUID | None,
        lease_owner: str,
        lease_seconds: int,
    ) -> SubmissionJob | None:
        statement = text(
            """
            WITH candidate AS (
                SELECT sa.id
                  FROM submission_attempts sa
                 WHERE sa.submission_id = :submission_id
                   AND (CAST(:attempt_id AS UUID) IS NULL AND sa.kind = 'initial'
                        OR sa.id = CAST(:attempt_id AS UUID))
                   AND sa.status IN ('Pending', 'Compiling', 'Running')
                   AND (sa.lease_expires_at IS NULL OR sa.lease_expires_at < now()
                        OR sa.lease_owner = :lease_owner)
                   AND NOT EXISTS (
                       SELECT 1 FROM rejudge_task_items ri
                       JOIN rejudge_tasks rt ON rt.id = ri.task_id
                       WHERE ri.attempt_id = sa.id AND rt.status = 'paused'
                   )
                 ORDER BY sa.sequence DESC
                 LIMIT 1
                 FOR UPDATE SKIP LOCKED
            ), claimed AS (
                UPDATE submission_attempts sa
                   SET lease_owner = :lease_owner,
                       lease_expires_at = now() + make_interval(secs => :lease_seconds),
                       started_at = COALESCE(sa.started_at, now()),
                       updated_at = now()
                  FROM candidate
                 WHERE sa.id = candidate.id
                RETURNING sa.*
            )
            SELECT s.id, s.problem_id, l.slug AS language,
                   claimed.status::text AS status, s.mode::text AS mode,
                   s.source_object_key, s.source_checksum,
                   s.custom_input_object_key, s.custom_input_checksum, claimed.test_set_id,
                   claimed.problem_version, claimed.time_limit_ms_snapshot,
                   claimed.memory_limit_mb_snapshot,
                   COALESCE(ts.checker_type::text, 'exact') AS checker_type,
                   ts.absolute_tolerance, ts.relative_tolerance,
                   claimed.id AS attempt_id, claimed.kind AS attempt_kind
              FROM claimed
              JOIN submissions s ON s.id = claimed.submission_id
              JOIN languages l ON l.id = s.language_id
              LEFT JOIN test_sets ts ON ts.id = claimed.test_set_id
            """
        )
        try:
            async with self.engine.begin() as connection:
                row = (
                    await connection.execute(
                        statement,
                        {
                            "submission_id": submission_id,
                            "attempt_id": attempt_id,
                            "lease_owner": lease_owner,
                            "lease_seconds": lease_seconds,
                        },
                    )
                ).mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL attempt claim failed") from exc
        return self._to_job(row)

    async def load_submission(
        self, submission_id: UUID, attempt_id: UUID | None = None
    ) -> SubmissionJob | None:
        statement = text(
            """
            SELECT s.id, s.problem_id, l.slug AS language,
                   sa.status::text AS status, s.mode::text AS mode,
                   s.source_object_key, s.source_checksum,
                   s.custom_input_object_key, s.custom_input_checksum, sa.test_set_id,
                   sa.problem_version, sa.time_limit_ms_snapshot,
                   sa.memory_limit_mb_snapshot,
                   COALESCE(ts.checker_type::text, 'exact') AS checker_type,
                   ts.absolute_tolerance, ts.relative_tolerance,
                   sa.id AS attempt_id, sa.kind AS attempt_kind
              FROM submissions s
              JOIN languages l ON l.id = s.language_id
              JOIN submission_attempts sa ON sa.submission_id = s.id
              LEFT JOIN test_sets ts ON ts.id = sa.test_set_id
             WHERE s.id = :submission_id
               AND (CAST(:attempt_id AS UUID) IS NULL AND sa.kind = 'initial'
                    OR sa.id = CAST(:attempt_id AS UUID))
             ORDER BY sa.sequence DESC
             LIMIT 1
            """
        )
        try:
            async with self.engine.connect() as connection:
                row = (
                    await connection.execute(
                        statement,
                        {"submission_id": submission_id, "attempt_id": attempt_id},
                    )
                ).mappings().one_or_none()
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL submission lookup failed") from exc
        return self._to_job(row)

    @staticmethod
    def _to_job(row) -> SubmissionJob | None:
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
            custom_input_object_key=row["custom_input_object_key"],
            custom_input_checksum=row["custom_input_checksum"],
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
            attempt_id=row["attempt_id"],
            attempt_kind=row["attempt_kind"],
        )

    async def renew_lease(
        self, attempt_id: UUID, lease_owner: str, lease_seconds: int
    ) -> bool:
        statement = text(
            """
            UPDATE submission_attempts
               SET lease_expires_at = now() + make_interval(secs => :lease_seconds),
                   updated_at = now()
             WHERE id = :attempt_id AND lease_owner = :lease_owner
               AND status IN ('Pending', 'Compiling', 'Running')
            RETURNING id
            """
        )
        try:
            async with self.engine.begin() as connection:
                value = await connection.scalar(
                    statement,
                    {
                        "attempt_id": attempt_id,
                        "lease_owner": lease_owner,
                        "lease_seconds": lease_seconds,
                    },
                )
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL attempt lease renewal failed") from exc
        return value is not None

    async def release_lease(self, attempt_id: UUID, lease_owner: str) -> None:
        try:
            async with self.engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE submission_attempts SET lease_owner = NULL, "
                        "lease_expires_at = NULL, updated_at = now() "
                        "WHERE id = :attempt_id AND lease_owner = :lease_owner"
                    ),
                    {"attempt_id": attempt_id, "lease_owner": lease_owner},
                )
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL attempt lease release failed") from exc

    async def load_test_cases(self, job: SubmissionJob) -> list[TestCase]:
        if job.mode is SubmissionMode.SAMPLE:
            return await self._load_sample_case(job.problem_id)
        if job.mode is SubmissionMode.CUSTOM:
            return self._load_custom_case(job)
        if job.test_set_id is None:
            return []
        return await self._load_hidden_test_cases(job.test_set_id)

    @staticmethod
    def _load_custom_case(job: SubmissionJob) -> list[TestCase]:
        if not job.custom_input_object_key or not job.custom_input_checksum:
            return []
        case_id = uuid5(NAMESPACE_URL, f"codearena:submission:{job.id}:custom-input")
        return [
            TestCase(
                id=case_id,
                input_object_key=job.custom_input_object_key,
                output_object_key=None,
                checksum=job.custom_input_checksum,
                score=Decimal("0"),
                sequence=0,
                group_id=case_id,
                group_name="custom-input",
                group_sequence=0,
                group_score=Decimal("0"),
                custom_input=True,
            )
        ]

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
        case_id = uuid5(NAMESPACE_URL, f"codearena:problem:{problem_id}:sample")
        return [
            TestCase(
                id=case_id,
                input_object_key=None,
                output_object_key=None,
                checksum=hashlib.sha256(stdin + b"\0" + expected).hexdigest(),
                score=Decimal("100"),
                sequence=0,
                inline_input=stdin,
                inline_output=expected,
                group_id=case_id,
                group_name="sample",
                group_sequence=0,
                group_score=Decimal("100"),
            )
        ]

    async def _load_hidden_test_cases(self, test_set_id: UUID) -> list[TestCase]:
        statement = text(
            """
            SELECT tc.id, tc.input_object_key, tc.output_object_key, tc.checksum,
                   tc.score, tc.sequence, tg.id AS group_id, tg.name AS group_name,
                   tg.sequence AS group_sequence, tg.score AS group_score,
                   tg.short_circuit, tg.dependency_group_id
              FROM test_cases tc
              JOIN test_groups tg ON tg.id = tc.group_id
             WHERE tc.test_set_id = :test_set_id
             ORDER BY tg.sequence, tc.sequence
            """
        )
        try:
            async with self.engine.connect() as connection:
                rows = (
                    await connection.execute(statement, {"test_set_id": test_set_id})
                ).mappings().all()
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
                group_id=row["group_id"],
                group_name=row["group_name"],
                group_sequence=row["group_sequence"],
                group_score=Decimal(row["group_score"]),
                group_short_circuit=row["short_circuit"],
                dependency_group_id=row["dependency_group_id"],
            )
            for row in rows
        ]

    async def transition(
        self,
        job: SubmissionJob,
        expected: SubmissionStatus,
        next_status: SubmissionStatus,
        lease_owner: str,
    ) -> bool:
        if job.attempt_id is None:
            return False
        try:
            async with self.engine.begin() as connection:
                attempt = await connection.scalar(
                    text(
                        "UPDATE submission_attempts SET status = CAST(:next AS submission_status), "
                        "updated_at = now() WHERE id = :attempt_id "
                        "AND status = CAST(:expected AS submission_status) "
                        "AND lease_owner = :owner RETURNING id"
                    ),
                    {
                        "attempt_id": job.attempt_id,
                        "expected": expected.value,
                        "next": next_status.value,
                        "owner": lease_owner,
                    },
                )
                if attempt is None:
                    return False
                if job.attempt_kind == "initial":
                    submission = await connection.scalar(
                        text(
                            "UPDATE submissions SET status = CAST(:next AS submission_status), "
                            "updated_at = now() WHERE id = :submission_id "
                            "AND status = CAST(:expected AS submission_status) RETURNING id"
                        ),
                        {
                            "submission_id": job.id,
                            "expected": expected.value,
                            "next": next_status.value,
                        },
                    )
                    if submission is None:
                        raise InfrastructureError("submission and attempt states diverged")
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL status transition failed") from exc
        return True

    async def finalize(
        self,
        job: SubmissionJob,
        expected: SubmissionStatus,
        result: JudgeResult,
        lease_owner: str,
    ) -> bool:
        if job.attempt_id is None:
            return False
        passed = sum(item.status is SubmissionStatus.ACCEPTED for item in result.case_results)
        score = sum((item.score for item in result.group_results), Decimal("0"))
        judged_at = datetime.now(UTC)
        try:
            async with self.engine.begin() as connection:
                await connection.execute(
                    text(
                        "SELECT pg_advisory_xact_lock_shared("
                        "hashtext('codearena:training-statistics'))"
                    )
                )
                attempt = (
                    await connection.execute(
                        text(
                            """
                            UPDATE submission_attempts
                               SET status = CAST(:status AS submission_status),
                                   compiler_output = :compiler_output,
                                   error_message = :error_message,
                                   public_output = :public_output,
                                   time_used_ms = :time_used_ms,
                                   memory_used_kb = :memory_used_kb,
                                   passed_case_count = :passed,
                                   total_case_count = :total,
                                   score = :score, judged_at = :judged_at,
                                   lease_owner = NULL, lease_expires_at = NULL,
                                   updated_at = :judged_at
                             WHERE id = :attempt_id
                               AND status = CAST(:expected AS submission_status)
                               AND lease_owner = :owner
                            RETURNING submission_id, kind
                            """
                        ),
                        {
                            "attempt_id": job.attempt_id,
                            "expected": expected.value,
                            "owner": lease_owner,
                            "status": result.status.value,
                            "compiler_output": (result.compiler_output or "")[:16_384] or None,
                            "error_message": (result.error_message or "")[:2_000] or None,
                            "public_output": (result.public_output or "")[:16_384] or None,
                            "time_used_ms": result.time_used_ms,
                            "memory_used_kb": result.memory_used_kb,
                            "passed": passed,
                            "total": result.total_case_count,
                            "score": score,
                            "judged_at": judged_at,
                        },
                    )
                ).mappings().one_or_none()
                if attempt is None:
                    return False
                await self._insert_attempt_results(connection, job.attempt_id, result)

                effective = result.status is not SubmissionStatus.SYSTEM_ERROR
                if attempt["kind"] == "initial" or effective:
                    submission = (
                        await connection.execute(
                            text(
                                """
                                UPDATE submissions
                                   SET status = CAST(:status AS submission_status),
                                       effective_attempt_id = :attempt_id,
                                       compiler_output = :compiler_output,
                                       error_message = :error_message,
                                       sample_output = :public_output,
                                       time_used_ms = :time_used_ms,
                                       memory_used_kb = :memory_used_kb,
                                       passed_case_count = :passed,
                                       total_case_count = :total,
                                       score = :score, judged_at = :judged_at,
                                       updated_at = :judged_at
                                 WHERE id = :submission_id
                                   AND (:kind <> 'initial'
                                        OR status = CAST(:expected AS submission_status))
                                RETURNING user_id, problem_id, mode::text AS mode
                                """
                            ),
                            {
                                "submission_id": job.id,
                                "kind": attempt["kind"],
                                "expected": expected.value,
                                "status": result.status.value,
                                "attempt_id": job.attempt_id,
                                "compiler_output": (result.compiler_output or "")[:16_384]
                                or None,
                                "error_message": (result.error_message or "")[:2_000] or None,
                                "public_output": (result.public_output or "")[:16_384] or None,
                                "time_used_ms": result.time_used_ms,
                                "memory_used_kb": result.memory_used_kb,
                                "passed": passed,
                                "total": result.total_case_count,
                                "score": score,
                                "judged_at": judged_at,
                            },
                        )
                    ).mappings().one_or_none()
                    if submission is None:
                        raise InfrastructureError("submission finalization condition failed")
                    await self._replace_effective_case_results(
                        connection, job.id, result, submission["mode"]
                    )
                    if (
                        submission["mode"] == SubmissionMode.JUDGE.value
                        and result.status is not SubmissionStatus.SYSTEM_ERROR
                    ):
                        await self._rebuild_statistics(
                            connection,
                            job.id,
                            submission["user_id"],
                            submission["problem_id"],
                            result.status,
                            judged_at,
                        )
                await connection.execute(
                    text(
                        "UPDATE rejudge_tasks rt SET status = CASE "
                        "WHEN rt.status='paused' THEN 'paused' "
                        "WHEN EXISTS (SELECT 1 FROM rejudge_task_items i JOIN "
                        "submission_attempts a "
                        "ON a.id=i.attempt_id WHERE i.task_id=rt.id AND a.status IN "
                        "('Pending','Compiling','Running')) THEN 'running' "
                        "WHEN EXISTS (SELECT 1 FROM rejudge_task_items i JOIN "
                        "submission_attempts a "
                        "ON a.id=i.attempt_id WHERE i.task_id=rt.id AND a.status='System Error') "
                        "THEN 'completed_with_errors' ELSE 'completed' END, "
                        "completed_at = CASE WHEN NOT EXISTS (SELECT 1 FROM rejudge_task_items i "
                        "JOIN submission_attempts a ON a.id=i.attempt_id WHERE i.task_id=rt.id "
                        "AND a.status IN ('Pending','Compiling','Running')) "
                        "THEN now() ELSE NULL END "
                        "WHERE EXISTS (SELECT 1 FROM rejudge_task_items i WHERE i.task_id=rt.id "
                        "AND i.attempt_id=:attempt_id)"
                    ),
                    {"attempt_id": job.attempt_id},
                )
        except SQLAlchemyError as exc:
            raise InfrastructureError("PostgreSQL result finalization failed") from exc
        return True

    @staticmethod
    async def _insert_attempt_results(connection, attempt_id: UUID, result: JudgeResult) -> None:
        case_rows = [
            {
                "attempt_id": attempt_id,
                "test_case_id": item.test_case_id,
                "group_id": item.group_id,
                "status": item.status.value,
                "time": item.time_used_ms,
                "memory": item.memory_used_kb,
                "exit_code": item.exit_code,
            }
            for item in result.case_results
            if item.group_id is not None
        ]
        if case_rows:
            await connection.execute(
                text(
                    "INSERT INTO submission_attempt_case_results (attempt_id, test_case_id, "
                    "group_id, status, time_used_ms, memory_used_kb, exit_code) VALUES "
                    "(:attempt_id, :test_case_id, :group_id, CAST(:status AS submission_status), "
                    ":time, :memory, :exit_code) ON CONFLICT (attempt_id, test_case_id) DO NOTHING"
                ),
                case_rows,
            )
        if result.group_results:
            await connection.execute(
                text(
                    "INSERT INTO submission_attempt_group_results (attempt_id, group_id, status, "
                    "score, passed_case_count, total_case_count, skipped) VALUES "
                    "(:attempt_id, :group_id, CAST(:status AS submission_status), :score, "
                    ":passed, :total, :skipped) ON CONFLICT (attempt_id, group_id) DO NOTHING"
                ),
                [
                    {
                        "attempt_id": attempt_id,
                        "group_id": item.group_id,
                        "status": item.status.value,
                        "score": item.score,
                        "passed": item.passed_case_count,
                        "total": item.total_case_count,
                        "skipped": item.skipped,
                    }
                    for item in result.group_results
                ],
            )

    @staticmethod
    async def _replace_effective_case_results(
        connection, submission_id: UUID, result: JudgeResult, mode: str
    ) -> None:
        await connection.execute(
            text("DELETE FROM submission_case_results WHERE submission_id = :id"),
            {"id": submission_id},
        )
        if mode != SubmissionMode.JUDGE.value or not result.case_results:
            return
        await connection.execute(
            text(
                "INSERT INTO submission_case_results (submission_id, test_case_id, status, "
                "time_used_ms, memory_used_kb, exit_code, stdout_excerpt, stderr_excerpt) "
                "VALUES (:submission_id, :test_case_id, CAST(:status AS submission_status), "
                ":time, :memory, :exit_code, NULL, NULL)"
            ),
            [
                {
                    "submission_id": submission_id,
                    "test_case_id": item.test_case_id,
                    "status": item.status.value,
                    "time": item.time_used_ms,
                    "memory": item.memory_used_kb,
                    "exit_code": item.exit_code,
                }
                for item in result.case_results
            ],
        )

    @staticmethod
    async def _rebuild_statistics(
        connection,
        submission_id: UUID,
        user_id: UUID,
        problem_id: int,
        status: SubmissionStatus,
        judged_at: datetime,
    ) -> None:
        accepted = status is SubmissionStatus.ACCEPTED
        await connection.execute(
            text(
                "INSERT INTO submission_stat_events (submission_id,user_id,problem_id,"
                "terminal_status,accepted,applied_at) VALUES (:submission_id,:user_id,:problem_id,"
                "CAST(:status AS submission_status),:accepted,:at) ON CONFLICT (submission_id) "
                "DO UPDATE SET terminal_status=EXCLUDED.terminal_status, "
                "accepted=EXCLUDED.accepted, applied_at=EXCLUDED.applied_at"
            ),
            {
                "submission_id": submission_id,
                "user_id": user_id,
                "problem_id": problem_id,
                "status": status.value,
                "accepted": accepted,
                "at": judged_at,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO user_problem_progress (user_id,problem_id,attempt_count,accepted,"
                "first_accepted_at,last_submission_id,updated_at) SELECT :user_id,:problem_id,"
                "count(*),bool_or(accepted),min(applied_at) FILTER (WHERE accepted),"
                "(array_agg(submission_id ORDER BY applied_at DESC))[1],now() FROM "
                "submission_stat_events WHERE user_id=:user_id AND problem_id=:problem_id "
                "ON CONFLICT (user_id,problem_id) DO UPDATE SET "
                "attempt_count=EXCLUDED.attempt_count,"
                "accepted=EXCLUDED.accepted,first_accepted_at=EXCLUDED.first_accepted_at,"
                "last_submission_id=EXCLUDED.last_submission_id,updated_at=now()"
            ),
            {"user_id": user_id, "problem_id": problem_id},
        )
        await connection.execute(
            text(
                "UPDATE users SET submission_count=(SELECT count(*) FROM submission_stat_events "
                "WHERE user_id=:user_id), accepted_count=(SELECT count(*) FROM "
                "submission_stat_events WHERE user_id=:user_id AND accepted), solved_count=(SELECT "
                "count(DISTINCT problem_id) FROM submission_stat_events WHERE user_id=:user_id "
                "AND accepted) WHERE id=:user_id"
            ),
            {"user_id": user_id},
        )
        await connection.execute(
            text(
                "UPDATE problems SET submission_count=(SELECT count(*) FROM submission_stat_events "
                "WHERE problem_id=:problem_id), accepted_count=(SELECT count(*) FROM "
                "submission_stat_events WHERE problem_id=:problem_id AND accepted) "
                "WHERE id=:problem_id"
            ),
            {"problem_id": problem_id},
        )
        await connection.execute(
            text(
                """
                INSERT INTO user_exercise_progress (
                    user_id, exercise_id, status, selected_runtime, attempt_count,
                    v8_attempt_count, nodejs_attempt_count, v8_completed_at,
                    nodejs_completed_at, first_completed_at, last_attempted_at, updated_at
                )
                SELECT :user_id, exercises.id,
                       CAST(CASE WHEN bool_or(events.accepted) THEN 'completed'
                                 ELSE 'attempted' END AS exercise_progress_status),
                       (array_agg(languages.slug ORDER BY events.applied_at DESC,
                                  events.submission_id DESC))[1],
                       count(*)::integer,
                       count(*) FILTER (
                           WHERE languages.slug = 'javascript-v8')::integer,
                       count(*) FILTER (WHERE languages.slug = 'nodejs')::integer,
                       min(events.applied_at) FILTER (
                           WHERE events.accepted AND languages.slug = 'javascript-v8'),
                       min(events.applied_at) FILTER (
                           WHERE events.accepted AND languages.slug = 'nodejs'),
                       min(events.applied_at) FILTER (WHERE events.accepted),
                       max(events.applied_at), now()
                  FROM submission_stat_events events
                  JOIN submissions ON submissions.id = events.submission_id
                  JOIN languages ON languages.id = submissions.language_id
                  JOIN exercises ON exercises.problem_id = events.problem_id
                 WHERE events.user_id = :user_id
                   AND events.problem_id = :problem_id
                   AND languages.slug IN ('javascript-v8', 'nodejs')
                 GROUP BY exercises.id
                ON CONFLICT (user_id, exercise_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    selected_runtime = EXCLUDED.selected_runtime,
                    attempt_count = EXCLUDED.attempt_count,
                    v8_attempt_count = EXCLUDED.v8_attempt_count,
                    nodejs_attempt_count = EXCLUDED.nodejs_attempt_count,
                    v8_completed_at = EXCLUDED.v8_completed_at,
                    nodejs_completed_at = EXCLUDED.nodejs_completed_at,
                    first_completed_at = EXCLUDED.first_completed_at,
                    last_attempted_at = EXCLUDED.last_attempted_at,
                    updated_at = now()
                """
            ),
            {"user_id": user_id, "problem_id": problem_id},
        )


def create_repository(database_url: str) -> JudgeRepository:
    return JudgeRepository(database_url)
