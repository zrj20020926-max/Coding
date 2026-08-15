import asyncio
import hashlib
import os
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.domain.models import CaseResult, GroupResult, JudgeResult, SubmissionStatus
from app.infrastructure.database import JudgeRepository


async def create_initial_attempt(connection, submission_id: UUID) -> UUID:
    attempt_id = uuid4()
    await connection.execute(
        text(
            "INSERT INTO submission_attempts (id, submission_id, sequence, kind, status, "
            "problem_id, test_set_id, problem_version, time_limit_ms_snapshot, "
            "memory_limit_mb_snapshot) SELECT :attempt_id, id, 1, 'initial', 'Pending', "
            "problem_id, test_set_id, problem_version, time_limit_ms_snapshot, "
            "memory_limit_mb_snapshot FROM submissions WHERE id = :submission_id"
        ),
        {"attempt_id": attempt_id, "submission_id": submission_id},
    )
    await connection.execute(
        text("UPDATE submissions SET effective_attempt_id = :attempt_id WHERE id = :id"),
        {"attempt_id": attempt_id, "id": submission_id},
    )
    return attempt_id


async def claim_running(
    repository: JudgeRepository,
    submission_id: UUID,
    lease_owner: str,
):
    job = await repository.claim_submission(submission_id, None, lease_owner, 60)
    assert job is not None
    assert await repository.transition(
        job, SubmissionStatus.PENDING, SubmissionStatus.COMPILING, lease_owner
    )
    assert await repository.transition(
        job, SubmissionStatus.COMPILING, SubmissionStatus.RUNNING, lease_owner
    )
    return job


@pytest.mark.integration
@pytest.mark.asyncio
async def test_formal_and_sample_finalization_use_distinct_progress_rules() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    if not (make_url(database_url).database or "").endswith("_test"):
        pytest.fail("Integration tests require a database whose name ends with '_test'")

    engine = create_async_engine(database_url)
    repository = JudgeRepository(database_url)
    suffix = uuid4().hex[:10]
    user_id: UUID | None = None
    problem_id: int | None = None
    test_set_id: UUID | None = None
    test_group_id: UUID | None = None
    test_case_id: UUID | None = None
    judge_id: UUID | None = None
    sample_id: UUID | None = None
    try:
        async with engine.begin() as connection:
            user_id = await connection.scalar(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname) "
                    "VALUES (:username, :email, 'hash', 'judge integration') RETURNING id"
                ),
                {
                    "username": f"judge_{suffix}",
                    "email": f"judge-{suffix}@example.com",
                },
            )
            problem_id = await connection.scalar(
                text(
                    "INSERT INTO problems (slug, title, description, difficulty, "
                    "input_description, output_description, sample_input, sample_output, "
                    "visibility) VALUES (:slug, 'Judge integration', 'd', 'easy', 'i', "
                    "'o', '1 2\n', '3\n', 'public') RETURNING id"
                ),
                {"slug": f"judge-integration-{suffix}"},
            )
            language_id = await connection.scalar(
                text("SELECT id FROM languages WHERE slug = 'nodejs'")
            )
            test_set_id = await connection.scalar(
                text(
                    "INSERT INTO test_sets (problem_id, version, status, case_count, "
                    "total_score) VALUES (:problem_id, 1, 'draft', 0, 0) RETURNING id"
                ),
                {"problem_id": problem_id},
            )
            test_group_id = await connection.scalar(
                text(
                    "INSERT INTO test_groups (test_set_id, name, sequence, score) "
                    "VALUES (:test_set_id, 'default', 0, 100) RETURNING id"
                ),
                {"test_set_id": test_set_id},
            )
            test_case_id = await connection.scalar(
                text(
                    "INSERT INTO test_cases (test_set_id, group_id, input_object_key, "
                    "output_object_key, checksum, score, sequence) VALUES "
                    "(:test_set_id, :group_id, 'input', 'output', :checksum, "
                    "100, 0) RETURNING id"
                ),
                {
                    "test_set_id": test_set_id,
                    "group_id": test_group_id,
                    "checksum": "0" * 64,
                },
            )
            await connection.execute(
                text("UPDATE test_sets SET status = 'active' WHERE id = :id"),
                {"id": test_set_id},
            )
            common = {
                "user_id": user_id,
                "problem_id": problem_id,
                "language_id": language_id,
            }
            judge_id = await connection.scalar(
                text(
                    "INSERT INTO submissions (user_id, problem_id, language_id, status, "
                    "mode, source_object_key, source_checksum, test_set_id, "
                    "problem_version, time_limit_ms_snapshot, memory_limit_mb_snapshot) "
                    "VALUES (:user_id, :problem_id, :language_id, 'Pending', 'judge', "
                    "'source', :checksum, :test_set_id, 1, 1000, 256) RETURNING id"
                ),
                {**common, "checksum": "1" * 64, "test_set_id": test_set_id},
            )
            sample_id = await connection.scalar(
                text(
                    "INSERT INTO submissions (user_id, problem_id, language_id, status, "
                    "mode, source_object_key, source_checksum, problem_version, "
                    "time_limit_ms_snapshot, memory_limit_mb_snapshot) VALUES (:user_id, "
                    ":problem_id, :language_id, 'Pending', 'sample', 'source', "
                    ":checksum, 1, 1000, 256) RETURNING id"
                ),
                {**common, "checksum": "2" * 64},
            )
            await create_initial_attempt(connection, judge_id)
            await create_initial_attempt(connection, sample_id)

        assert judge_id is not None
        assert test_case_id is not None
        judge_owner = f"judge-test-{suffix}"
        sample_owner = f"sample-test-{suffix}"
        loaded_job = await claim_running(repository, judge_id, judge_owner)
        assert loaded_job is not None
        assert loaded_job.test_set_id == test_set_id
        assert loaded_job.problem_version == 1
        assert loaded_job.time_limit_ms == 1000
        assert loaded_job.memory_limit_mb == 256
        loaded_cases = await repository.load_test_cases(loaded_job)
        assert [item.id for item in loaded_cases] == [test_case_id]

        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE test_sets SET status = 'inactive' WHERE id = :id"),
                {"id": test_set_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO test_sets (problem_id, version, status, case_count, "
                    "total_score, activated_at) VALUES (:problem_id, 2, 'active', 1, 100, now())"
                ),
                {"problem_id": problem_id},
            )
            await connection.execute(
                text(
                    "UPDATE problems SET time_limit_ms = 5000, memory_limit_mb = 512 "
                    "WHERE id = :id"
                ),
                {"id": problem_id},
            )
        reloaded = await repository.load_submission(judge_id)
        assert reloaded is not None
        assert reloaded.test_set_id == test_set_id
        assert reloaded.time_limit_ms == 1000
        assert reloaded.memory_limit_mb == 256

        formal = JudgeResult(
            status=SubmissionStatus.ACCEPTED,
            case_results=[
                CaseResult(
                    test_case_id,
                    SubmissionStatus.ACCEPTED,
                    11,
                    2048,
                    0,
                    Decimal("100"),
                    test_group_id,
                )
            ],
            total_case_count=1,
        )
        assert await repository.finalize(
            loaded_job, SubmissionStatus.RUNNING, formal, judge_owner
        )

        assert sample_id is not None
        sample_job = await claim_running(repository, sample_id, sample_owner)
        ephemeral_case_id = uuid4()
        sample = JudgeResult(
            status=SubmissionStatus.ACCEPTED,
            case_results=[
                CaseResult(
                    ephemeral_case_id,
                    SubmissionStatus.ACCEPTED,
                    7,
                    1024,
                    0,
                    Decimal("100"),
                    ephemeral_case_id,
                )
            ],
            group_results=[
                GroupResult(
                    group_id=ephemeral_case_id,
                    status=SubmissionStatus.ACCEPTED,
                    score=Decimal("100"),
                    passed_case_count=1,
                    total_case_count=1,
                )
            ],
            total_case_count=1,
            public_output="3\n",
        )
        assert await repository.finalize(
            sample_job, SubmissionStatus.RUNNING, sample, sample_owner
        )

        async with engine.connect() as connection:
            progress = (
                await connection.execute(
                    text(
                        "SELECT attempt_count, accepted FROM user_problem_progress "
                        "WHERE user_id = :user_id AND problem_id = :problem_id"
                    ),
                    {"user_id": user_id, "problem_id": problem_id},
                )
            ).mappings().one()
            stats = (
                await connection.execute(
                    text(
                        "SELECT submission_count, accepted_count, solved_count "
                        "FROM users WHERE id = :user_id"
                    ),
                    {"user_id": user_id},
                )
            ).mappings().one()
            sample_row = (
                await connection.execute(
                    text(
                        "SELECT status::text AS status, sample_output FROM submissions "
                        "WHERE id = :submission_id"
                    ),
                    {"submission_id": sample_id},
                )
            ).mappings().one()
            sample_cases = await connection.scalar(
                text(
                    "SELECT count(*) FROM submission_case_results "
                    "WHERE submission_id = :submission_id"
                ),
                {"submission_id": sample_id},
            )
            sample_attempt_cases = await connection.scalar(
                text(
                    "SELECT count(*) FROM submission_attempt_case_results acr "
                    "JOIN submission_attempts a ON a.id=acr.attempt_id "
                    "WHERE a.submission_id=:submission_id"
                ),
                {"submission_id": sample_id},
            )
            sample_attempt_groups = await connection.scalar(
                text(
                    "SELECT count(*) FROM submission_attempt_group_results agr "
                    "JOIN submission_attempts a ON a.id=agr.attempt_id "
                    "WHERE a.submission_id=:submission_id"
                ),
                {"submission_id": sample_id},
            )

        assert progress == {"attempt_count": 1, "accepted": True}
        assert stats == {
            "submission_count": 1,
            "accepted_count": 1,
            "solved_count": 1,
        }
        assert sample_row == {"status": "Accepted", "sample_output": "3\n"}
        assert sample_cases == 0
        assert sample_attempt_cases == 0
        assert sample_attempt_groups == 0
    finally:
        async with engine.begin() as connection:
            if user_id is not None and problem_id is not None:
                await connection.execute(
                    text(
                        "DELETE FROM user_problem_progress "
                        "WHERE user_id = :user_id AND problem_id = :problem_id"
                    ),
                    {"user_id": user_id, "problem_id": problem_id},
                )
            for submission_id in (judge_id, sample_id):
                if submission_id is not None:
                    await connection.execute(
                        text("DELETE FROM submissions WHERE id = :submission_id"),
                    {"submission_id": submission_id},
                )
            if test_set_id is not None:
                await connection.execute(
                    text("UPDATE test_sets SET status = 'draft' WHERE id = :test_set_id"),
                    {"test_set_id": test_set_id},
                )
            if test_case_id is not None:
                await connection.execute(
                    text("DELETE FROM test_cases WHERE id = :test_case_id"),
                    {"test_case_id": test_case_id},
                )
            if test_set_id is not None:
                await connection.execute(
                    text("DELETE FROM test_sets WHERE id = :test_set_id"),
                    {"test_set_id": test_set_id},
                )
            if problem_id is not None:
                await connection.execute(
                    text("UPDATE test_sets SET status = 'draft' WHERE problem_id = :problem_id"),
                    {"problem_id": problem_id},
                )
                await connection.execute(
                    text("DELETE FROM problems WHERE id = :problem_id"),
                    {"problem_id": problem_id},
                )
            if user_id is not None:
                await connection.execute(
                    text("DELETE FROM users WHERE id = :user_id"),
                    {"user_id": user_id},
                )
        await repository.close()
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_accepts_and_duplicate_terminal_events_are_idempotent() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    if not (make_url(database_url).database or "").endswith("_test"):
        pytest.fail("Integration tests require a database whose name ends with '_test'")

    engine = create_async_engine(database_url)
    repository = JudgeRepository(database_url)
    suffix = uuid4().hex[:10]
    user_id: UUID | None = None
    problem_id: int | None = None
    test_set_id: UUID | None = None
    submission_ids: list[UUID] = []
    jobs = []
    try:
        async with engine.begin() as connection:
            user_id = await connection.scalar(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname) "
                    "VALUES (:username, :email, 'hash', 'concurrency') RETURNING id"
                ),
                {
                    "username": f"concurrent_{suffix}",
                    "email": f"concurrent-{suffix}@example.com",
                },
            )
            problem_id = await connection.scalar(
                text(
                    "INSERT INTO problems (slug, title, description, difficulty, "
                    "input_description, output_description, visibility) VALUES "
                    "(:slug, 'Concurrent', 'd', 'medium', 'i', 'o', 'public') "
                    "RETURNING id"
                ),
                {"slug": f"concurrent-{suffix}"},
            )
            language_id = await connection.scalar(
                text("SELECT id FROM languages WHERE slug = 'nodejs'")
            )
            test_set_id = await connection.scalar(
                text(
                    "INSERT INTO test_sets (problem_id, version, status, case_count, "
                    "total_score) VALUES (:problem_id, 1, 'active', 1, 100) RETURNING id"
                ),
                {"problem_id": problem_id},
            )
            for index in range(2):
                submission_id = await connection.scalar(
                    text(
                        "INSERT INTO submissions (user_id, problem_id, language_id, "
                        "status, mode, source_object_key, source_checksum, test_set_id, "
                        "problem_version, time_limit_ms_snapshot, memory_limit_mb_snapshot) VALUES "
                        "(:user_id, :problem_id, :language_id, 'Pending', 'judge', "
                        ":object_key, :checksum, :test_set_id, 1, 1000, 256) RETURNING id"
                    ),
                    {
                        "user_id": user_id,
                        "problem_id": problem_id,
                        "language_id": language_id,
                        "object_key": f"source/{index}",
                        "checksum": str(index + 3) * 64,
                        "test_set_id": test_set_id,
                    },
                )
                assert submission_id is not None
                submission_ids.append(submission_id)
                await create_initial_attempt(connection, submission_id)

        for index, submission_id in enumerate(submission_ids):
            jobs.append(
                await claim_running(repository, submission_id, f"concurrent-{suffix}-{index}")
            )

        accepted = JudgeResult(
            status=SubmissionStatus.ACCEPTED,
            case_results=[],
            total_case_count=0,
        )
        finalized = await asyncio.gather(
            *(
                repository.finalize(
                    job,
                    SubmissionStatus.RUNNING,
                    accepted,
                    f"concurrent-{suffix}-{index}",
                )
                for index, job in enumerate(jobs)
            )
        )
        assert finalized == [True, True]
        assert not await repository.finalize(
            jobs[0],
            SubmissionStatus.RUNNING,
            accepted,
            f"concurrent-{suffix}-0",
        )

        async with engine.connect() as connection:
            progress = (
                await connection.execute(
                    text(
                        "SELECT attempt_count, accepted FROM user_problem_progress "
                        "WHERE user_id = :user_id AND problem_id = :problem_id"
                    ),
                    {"user_id": user_id, "problem_id": problem_id},
                )
            ).mappings().one()
            user_stats = (
                await connection.execute(
                    text(
                        "SELECT submission_count, accepted_count, solved_count FROM users "
                        "WHERE id = :user_id"
                    ),
                    {"user_id": user_id},
                )
            ).mappings().one()
            problem_stats = (
                await connection.execute(
                    text(
                        "SELECT submission_count, accepted_count FROM problems "
                        "WHERE id = :problem_id"
                    ),
                    {"problem_id": problem_id},
                )
            ).mappings().one()
            event_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM submission_stat_events "
                    "WHERE user_id = :user_id AND problem_id = :problem_id"
                ),
                {"user_id": user_id, "problem_id": problem_id},
            )

        assert progress == {"attempt_count": 2, "accepted": True}
        assert user_stats == {
            "submission_count": 2,
            "accepted_count": 2,
            "solved_count": 1,
        }
        assert problem_stats == {"submission_count": 2, "accepted_count": 2}
        assert event_count == 2
    finally:
        async with engine.begin() as connection:
            if user_id is not None:
                await connection.execute(
                    text("DELETE FROM submissions WHERE user_id = :user_id"),
                    {"user_id": user_id},
                )
            if problem_id is not None:
                await connection.execute(
                    text("UPDATE test_sets SET status = 'draft' WHERE problem_id = :problem_id"),
                    {"problem_id": problem_id},
                )
                await connection.execute(
                    text("DELETE FROM problems WHERE id = :problem_id"),
                    {"problem_id": problem_id},
                )
            if user_id is not None:
                await connection.execute(
                    text("DELETE FROM users WHERE id = :user_id"),
                    {"user_id": user_id},
                )
        await repository.close()
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_learning_progress_tracks_runtimes_and_excludes_sample_and_system_error() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    if not (make_url(database_url).database or "").endswith("_test"):
        pytest.fail("Integration tests require a database whose name ends with '_test'")

    engine = create_async_engine(database_url)
    repository = JudgeRepository(database_url)
    suffix = uuid4().hex[:10]
    user_id: UUID | None = None
    problem_id: int | None = None
    test_set_id: UUID | None = None
    course_id: int | None = None
    exercise_id: int | None = None
    submission_ids: list[UUID] = []
    try:
        async with engine.begin() as connection:
            user_id = await connection.scalar(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname) "
                    "VALUES (:username, :email, 'hash', 'learning progress') RETURNING id"
                ),
                {
                    "username": f"learning_{suffix}",
                    "email": f"learning-{suffix}@example.com",
                },
            )
            problem_id = await connection.scalar(
                text(
                    "INSERT INTO problems (slug, title, description, difficulty, "
                    "input_description, output_description, visibility) VALUES "
                    "(:slug, 'Learning progress', 'd', 'easy', 'i', 'o', 'public') "
                    "RETURNING id"
                ),
                {"slug": f"learning-progress-{suffix}"},
            )
            test_set_id = await connection.scalar(
                text(
                    "INSERT INTO test_sets (problem_id, version, status, case_count, "
                    "total_score) VALUES (:problem_id, 1, 'active', 0, 0) RETURNING id"
                ),
                {"problem_id": problem_id},
            )
            course_id = await connection.scalar(
                text(
                    "INSERT INTO courses (slug, title, description, type, sort_order, "
                    "is_public) VALUES (:slug, 'learning', 'learning', 'input', 9000, true) "
                    "RETURNING id"
                ),
                {"slug": f"learning-course-{suffix}"},
            )
            chapter_id = await connection.scalar(
                text(
                    "INSERT INTO chapters (course_id, slug, title, description, sort_order, "
                    "estimated_minutes, is_public) VALUES (:course_id, :slug, 'learning', "
                    "'learning', 1, 10, true) RETURNING id"
                ),
                {"course_id": course_id, "slug": f"learning-chapter-{suffix}"},
            )
            exercise_id = await connection.scalar(
                text(
                    "INSERT INTO exercises (problem_id, chapter_id, sort_order, "
                    "learning_objectives, v8_notes, nodejs_notes, common_mistakes, "
                    "starter_code_v8, starter_code_nodejs, estimated_minutes) VALUES "
                    "(:problem_id, :chapter_id, 1, 'learn', 'v8', 'node', '[]'::jsonb, "
                    "'print(1)', 'console.log(1)', 10) RETURNING id"
                ),
                {"problem_id": problem_id, "chapter_id": chapter_id},
            )
            language_ids = dict(
                (
                    await connection.execute(
                        text(
                            "SELECT slug, id FROM languages "
                            "WHERE slug IN ('javascript-v8', 'nodejs')"
                        )
                    )
                ).all()
            )

            async def create_submission(language: str, mode: str = "judge") -> UUID:
                custom_input_key = f"submission-inputs/{uuid4()}" if mode == "custom" else None
                custom_input_checksum = (
                    hashlib.sha256(b"custom stdin\n").hexdigest()
                    if mode == "custom"
                    else None
                )
                submission_id = await connection.scalar(
                    text(
                        "INSERT INTO submissions (user_id, problem_id, language_id, status, "
                        "mode, source_object_key, source_checksum, test_set_id, problem_version, "
                        "time_limit_ms_snapshot, memory_limit_mb_snapshot, "
                        "custom_input_object_key, custom_input_checksum, custom_input_size_bytes) "
                        "VALUES (:user_id, "
                        ":problem_id, :language_id, 'Pending', CAST(:mode AS submission_mode), "
                        ":object_key, :checksum, :test_set_id, 1, 1000, 256, "
                        ":custom_input_key, :custom_input_checksum, :custom_input_size) "
                        "RETURNING id"
                    ),
                    {
                        "user_id": user_id,
                        "problem_id": problem_id,
                        "language_id": language_ids[language],
                        "mode": mode,
                        "object_key": f"source/{uuid4()}",
                        "checksum": uuid4().hex * 2,
                        "test_set_id": test_set_id if mode == "judge" else None,
                        "custom_input_key": custom_input_key,
                        "custom_input_checksum": custom_input_checksum,
                        "custom_input_size": 13 if mode == "custom" else None,
                    },
                )
                await create_initial_attempt(connection, submission_id)
                submission_ids.append(submission_id)
                return submission_id

            v8_accepted = await create_submission("javascript-v8")
            node_wrong = await create_submission("nodejs")
            node_accepted = await create_submission("nodejs")
            v8_system_error = await create_submission("javascript-v8")
            sample_accepted = await create_submission("nodejs", "sample")
            custom_accepted = await create_submission("javascript-v8", "custom")

        async def finalize(submission_id: UUID, status: SubmissionStatus) -> bool:
            owner = f"learning-{submission_id}"
            job = await claim_running(repository, submission_id, owner)
            return await repository.finalize(
                job,
                SubmissionStatus.RUNNING,
                JudgeResult(status=status, total_case_count=0),
                owner,
            )

        assert await finalize(v8_accepted, SubmissionStatus.ACCEPTED)
        assert not await repository.finalize(
            await repository.load_submission(v8_accepted),
            SubmissionStatus.RUNNING,
            JudgeResult(status=SubmissionStatus.ACCEPTED),
            "duplicate-owner",
        )
        assert await finalize(node_wrong, SubmissionStatus.WRONG_ANSWER)
        assert await finalize(node_accepted, SubmissionStatus.ACCEPTED)
        assert await finalize(v8_system_error, SubmissionStatus.SYSTEM_ERROR)
        assert await finalize(sample_accepted, SubmissionStatus.ACCEPTED)
        assert await finalize(custom_accepted, SubmissionStatus.ACCEPTED)

        async with engine.connect() as connection:
            progress = (
                await connection.execute(
                    text(
                        "SELECT status::text AS status, selected_runtime, attempt_count, "
                        "v8_attempt_count, nodejs_attempt_count, v8_completed_at IS NOT NULL "
                        "AS v8_completed, nodejs_completed_at IS NOT NULL AS nodejs_completed "
                        "FROM user_exercise_progress WHERE user_id=:user_id "
                        "AND exercise_id=:exercise_id"
                    ),
                    {"user_id": user_id, "exercise_id": exercise_id},
                )
            ).mappings().one()
            event_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM submission_stat_events "
                    "WHERE user_id=:user_id AND problem_id=:problem_id"
                ),
                {"user_id": user_id, "problem_id": problem_id},
            )
        assert progress == {
            "status": "completed",
            "selected_runtime": "nodejs",
            "attempt_count": 3,
            "v8_attempt_count": 1,
            "nodejs_attempt_count": 2,
            "v8_completed": True,
            "nodejs_completed": True,
        }
        assert event_count == 3
    finally:
        async with engine.begin() as connection:
            if user_id is not None and exercise_id is not None:
                await connection.execute(
                    text(
                        "DELETE FROM user_exercise_progress WHERE user_id=:user_id "
                        "AND exercise_id=:exercise_id"
                    ),
                    {"user_id": user_id, "exercise_id": exercise_id},
                )
            for submission_id in submission_ids:
                await connection.execute(
                    text("DELETE FROM submissions WHERE id=:submission_id"),
                    {"submission_id": submission_id},
                )
            if exercise_id is not None:
                await connection.execute(
                    text("DELETE FROM exercises WHERE id=:exercise_id"),
                    {"exercise_id": exercise_id},
                )
            if course_id is not None:
                await connection.execute(
                    text("DELETE FROM courses WHERE id=:course_id"),
                    {"course_id": course_id},
                )
            if test_set_id is not None:
                await connection.execute(
                    text("UPDATE test_sets SET status='draft' WHERE id=:test_set_id"),
                    {"test_set_id": test_set_id},
                )
                await connection.execute(
                    text("DELETE FROM test_sets WHERE id=:test_set_id"),
                    {"test_set_id": test_set_id},
                )
            if problem_id is not None:
                await connection.execute(
                    text("DELETE FROM problems WHERE id=:problem_id"),
                    {"problem_id": problem_id},
                )
            if user_id is not None:
                await connection.execute(
                    text("DELETE FROM users WHERE id=:user_id"),
                    {"user_id": user_id},
                )
        await repository.close()
        await engine.dispose()
