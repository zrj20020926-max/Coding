import asyncio
import os
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.domain.models import CaseResult, JudgeResult, SubmissionStatus
from app.infrastructure.database import JudgeRepository


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
                text("SELECT id FROM languages WHERE slug = 'python'")
            )
            test_case_id = await connection.scalar(
                text(
                    "INSERT INTO test_cases (problem_id, input_object_key, "
                    "output_object_key, checksum, score, sequence) VALUES "
                    "(:problem_id, 'input', 'output', :checksum, 100, 0) RETURNING id"
                ),
                {"problem_id": problem_id, "checksum": "0" * 64},
            )
            common = {
                "user_id": user_id,
                "problem_id": problem_id,
                "language_id": language_id,
            }
            judge_id = await connection.scalar(
                text(
                    "INSERT INTO submissions (user_id, problem_id, language_id, status, "
                    "mode, source_object_key, source_checksum) VALUES (:user_id, "
                    ":problem_id, :language_id, 'Running', 'judge', 'source', "
                    ":checksum) RETURNING id"
                ),
                {**common, "checksum": "1" * 64},
            )
            sample_id = await connection.scalar(
                text(
                    "INSERT INTO submissions (user_id, problem_id, language_id, status, "
                    "mode, source_object_key, source_checksum) VALUES (:user_id, "
                    ":problem_id, :language_id, 'Running', 'sample', 'source', "
                    ":checksum) RETURNING id"
                ),
                {**common, "checksum": "2" * 64},
            )

        assert judge_id is not None
        assert test_case_id is not None
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
                )
            ],
            total_case_count=1,
        )
        assert await repository.finalize(judge_id, SubmissionStatus.RUNNING, formal)

        assert sample_id is not None
        sample = JudgeResult(
            status=SubmissionStatus.ACCEPTED,
            case_results=[
                CaseResult(
                    uuid4(),
                    SubmissionStatus.ACCEPTED,
                    7,
                    1024,
                    0,
                    Decimal("100"),
                )
            ],
            total_case_count=1,
            public_output="3\n",
        )
        assert await repository.finalize(sample_id, SubmissionStatus.RUNNING, sample)

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

        assert progress == {"attempt_count": 1, "accepted": True}
        assert stats == {
            "submission_count": 1,
            "accepted_count": 1,
            "solved_count": 1,
        }
        assert sample_row == {"status": "Accepted", "sample_output": "3\n"}
        assert sample_cases == 0
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
            if test_case_id is not None:
                await connection.execute(
                    text("DELETE FROM test_cases WHERE id = :test_case_id"),
                    {"test_case_id": test_case_id},
                )
            if problem_id is not None:
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
    submission_ids: list[UUID] = []
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
                text("SELECT id FROM languages WHERE slug = 'python'")
            )
            for index in range(2):
                submission_id = await connection.scalar(
                    text(
                        "INSERT INTO submissions (user_id, problem_id, language_id, "
                        "status, mode, source_object_key, source_checksum) VALUES "
                        "(:user_id, :problem_id, :language_id, 'Running', 'judge', "
                        ":object_key, :checksum) RETURNING id"
                    ),
                    {
                        "user_id": user_id,
                        "problem_id": problem_id,
                        "language_id": language_id,
                        "object_key": f"source/{index}",
                        "checksum": str(index + 3) * 64,
                    },
                )
                assert submission_id is not None
                submission_ids.append(submission_id)

        accepted = JudgeResult(
            status=SubmissionStatus.ACCEPTED,
            case_results=[],
            total_case_count=0,
        )
        finalized = await asyncio.gather(
            *(
                repository.finalize(
                    submission_id,
                    SubmissionStatus.RUNNING,
                    accepted,
                )
                for submission_id in submission_ids
            )
        )
        assert finalized == [True, True]
        assert not await repository.finalize(
            submission_ids[0], SubmissionStatus.RUNNING, accepted
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
