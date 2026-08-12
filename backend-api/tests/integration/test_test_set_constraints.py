import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def seed_problem(connection, suffix: str) -> tuple[int, object, int]:
    user_id = await connection.scalar(
        text(
            "INSERT INTO users (username, email, password_hash, nickname) "
            "VALUES (:username, :email, 'hash', 'test sets') RETURNING id"
        ),
        {"username": f"testset_{suffix}", "email": f"testset-{suffix}@example.com"},
    )
    problem_id = await connection.scalar(
        text(
            "INSERT INTO problems (slug, title, description, difficulty, "
            "input_description, output_description, visibility) VALUES "
            "(:slug, 'sets', 'd', 'easy', 'i', 'o', 'draft') RETURNING id"
        ),
        {"slug": f"test-sets-{suffix}"},
    )
    language_id = await connection.scalar(text("SELECT id FROM languages WHERE slug = 'python'"))
    return problem_id, user_id, language_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_only_one_active_test_set_per_problem(postgres_database_url: str) -> None:
    engine = create_async_engine(postgres_database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        problem_id, _, _ = await seed_problem(connection, uuid4().hex[:10])
        await connection.execute(
            text(
                "INSERT INTO test_sets (problem_id, version, status, case_count, total_score) "
                "VALUES (:problem_id, 1, 'active', 1, 100)"
            ),
            {"problem_id": problem_id},
        )
        with pytest.raises(IntegrityError):
            await connection.execute(
                text(
                    "INSERT INTO test_sets (problem_id, version, status, case_count, total_score) "
                    "VALUES (:problem_id, 2, 'active', 1, 100)"
                ),
                {"problem_id": problem_id},
            )
        await transaction.rollback()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_referenced_test_set_cases_and_submission_snapshot_are_immutable(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        problem_id, user_id, language_id = await seed_problem(connection, uuid4().hex[:10])
        test_set_id = await connection.scalar(
            text(
                "INSERT INTO test_sets (problem_id, version, status, case_count, total_score) "
                "VALUES (:problem_id, 1, 'active', 1, 100) RETURNING id"
            ),
            {"problem_id": problem_id},
        )
        # The trigger only allows case changes in draft/invalid sets, so seed via a draft.
        await connection.execute(
            text("UPDATE test_sets SET status = 'draft' WHERE id = :id"),
            {"id": test_set_id},
        )
        case_id = await connection.scalar(
            text(
                "INSERT INTO test_cases (test_set_id, input_object_key, output_object_key, "
                "checksum, score, sequence) VALUES (:id, 'private/input', "
                "'private/output', :checksum, 100, 1) RETURNING id"
            ),
            {"id": test_set_id, "checksum": "a" * 64},
        )
        await connection.execute(
            text("UPDATE test_sets SET status = 'active', activated_at = now() WHERE id = :id"),
            {"id": test_set_id},
        )
        submission_id = await connection.scalar(
            text(
                "INSERT INTO submissions (user_id, problem_id, language_id, mode, "
                "test_set_id, problem_version, time_limit_ms_snapshot, "
                "memory_limit_mb_snapshot, source_object_key, source_checksum) VALUES "
                "(:user_id, :problem_id, :language_id, 'judge', :test_set_id, 1, "
                "1000, 256, 'source', :checksum) RETURNING id"
            ),
            {
                "user_id": user_id,
                "problem_id": problem_id,
                "language_id": language_id,
                "test_set_id": test_set_id,
                "checksum": "b" * 64,
            },
        )
        for statement, values in (
            ("UPDATE test_sets SET checker_type = 'token' WHERE id = :id", {"id": test_set_id}),
            ("UPDATE test_cases SET score = 99 WHERE id = :id", {"id": case_id}),
            (
                "UPDATE submissions SET time_limit_ms_snapshot = 2000 WHERE id = :id",
                {"id": submission_id},
            ),
        ):
            savepoint = await connection.begin_nested()
            with pytest.raises(IntegrityError):
                await connection.execute(text(statement), values)
            await savepoint.rollback()

        second_id = await connection.scalar(
            text(
                "INSERT INTO test_sets (problem_id, version, status, case_count, total_score) "
                "VALUES (:problem_id, 2, 'ready', 1, 100) RETURNING id"
            ),
            {"problem_id": problem_id},
        )
        await connection.execute(
            text("UPDATE test_sets SET status = 'inactive' WHERE id = :id"),
            {"id": test_set_id},
        )
        await connection.execute(
            text("UPDATE test_sets SET status = 'active', activated_at = now() WHERE id = :id"),
            {"id": second_id},
        )
        snapshot = (
            await connection.execute(
                text(
                    "SELECT test_set_id, time_limit_ms_snapshot, memory_limit_mb_snapshot "
                    "FROM submissions WHERE id = :id"
                ),
                {"id": submission_id},
            )
        ).mappings().one()
        assert snapshot == {
            "test_set_id": test_set_id,
            "time_limit_ms_snapshot": 1000,
            "memory_limit_mb_snapshot": 256,
        }
        await transaction.rollback()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_only_unreferenced_draft_test_set_can_be_deleted(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        problem_id, _, _ = await seed_problem(connection, uuid4().hex[:10])
        draft_id = await connection.scalar(
            text(
                "INSERT INTO test_sets (problem_id, version, status) "
                "VALUES (:problem_id, 1, 'draft') RETURNING id"
            ),
            {"problem_id": problem_id},
        )
        invalid_id = await connection.scalar(
            text(
                "INSERT INTO test_sets (problem_id, version, status) "
                "VALUES (:problem_id, 2, 'invalid') RETURNING id"
            ),
            {"problem_id": problem_id},
        )
        await connection.execute(
            text("DELETE FROM test_sets WHERE id = :id"), {"id": draft_id}
        )
        savepoint = await connection.begin_nested()
        with pytest.raises(IntegrityError):
            await connection.execute(
                text("DELETE FROM test_sets WHERE id = :id"), {"id": invalid_id}
            )
        await savepoint.rollback()
        await transaction.rollback()
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_activation_keeps_one_active_version(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        problem_id, _, _ = await seed_problem(connection, uuid4().hex[:10])
        ids = (
            await connection.execute(
                text(
                    "INSERT INTO test_sets (problem_id, version, status, case_count, "
                    "total_score) VALUES (:problem_id, 1, 'ready', 1, 100), "
                    "(:problem_id, 2, 'ready', 1, 100) RETURNING id"
                ),
                {"problem_id": problem_id},
            )
        ).scalars().all()

    async def activate(test_set_id: UUID) -> None:
        async with session_factory() as session:
            # Match the service lock order: problem first, then selected version.
            await session.execute(
                text("SELECT id FROM problems WHERE id = :id FOR UPDATE"),
                {"id": problem_id},
            )
            await session.execute(
                text(
                    "UPDATE test_sets SET status = 'inactive' "
                    "WHERE problem_id = :problem_id AND status = 'active'"
                ),
                {"problem_id": problem_id},
            )
            await session.execute(
                text(
                    "UPDATE test_sets SET status = 'active', activated_at = now() "
                    "WHERE id = :id"
                ),
                {"id": test_set_id},
            )
            await session.commit()

    await asyncio.gather(*(activate(test_set_id) for test_set_id in ids))
    async with engine.connect() as connection:
        active_count = await connection.scalar(
            text(
                "SELECT count(*) FROM test_sets "
                "WHERE problem_id = :problem_id AND status = 'active'"
            ),
            {"problem_id": problem_id},
        )
        assert active_count == 1
    async with engine.begin() as connection:
        await connection.execute(
            text("UPDATE test_sets SET status = 'draft' WHERE problem_id = :id"),
            {"id": problem_id},
        )
        await connection.execute(
            text("DELETE FROM problems WHERE id = :id"), {"id": problem_id}
        )
    await engine.dispose()
