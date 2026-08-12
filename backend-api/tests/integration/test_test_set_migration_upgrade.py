import asyncio
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.migration_bootstrap import make_alembic_config


async def _create_database(admin_url: str, database_name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        await engine.dispose()


async def _drop_database(admin_url: str, database_name: str) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
    finally:
        await engine.dispose()


async def _seed_legacy_schema(database_url: str) -> dict[str, object]:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            user_id = await connection.scalar(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname) "
                    "VALUES (:username, :email, 'hash', 'legacy') RETURNING id"
                ),
                {
                    "username": f"legacy_{uuid4().hex[:10]}",
                    "email": f"legacy-{uuid4().hex[:10]}@example.com",
                },
            )
            problem_id = await connection.scalar(
                text(
                    "INSERT INTO problems (slug, title, description, difficulty, "
                    "input_description, output_description, visibility, time_limit_ms, "
                    "memory_limit_mb) VALUES (:slug, 'legacy', 'd', 'easy', 'i', 'o', "
                    "'public', 2300, 384) RETURNING id"
                ),
                {"slug": f"legacy-{uuid4().hex[:10]}"},
            )
            language_id = await connection.scalar(
                text("SELECT id FROM languages WHERE slug = 'python'")
            )
            hidden_case_id = await connection.scalar(
                text(
                    "INSERT INTO test_cases (problem_id, input_object_key, "
                    "output_object_key, checksum, score, sequence, is_sample, is_hidden) "
                    "VALUES (:problem_id, 'hidden/input', 'hidden/output', :checksum, "
                    "100, 0, false, true) RETURNING id"
                ),
                {"problem_id": problem_id, "checksum": "a" * 64},
            )
            sample_case_id = await connection.scalar(
                text(
                    "INSERT INTO test_cases (problem_id, input_object_key, "
                    "output_object_key, checksum, score, sequence, is_sample, is_hidden) "
                    "VALUES (:problem_id, 'sample/input', 'sample/output', :checksum, "
                    "0, 1, true, false) RETURNING id"
                ),
                {"problem_id": problem_id, "checksum": "b" * 64},
            )
            submission_id = await connection.scalar(
                text(
                    "INSERT INTO submissions (user_id, problem_id, language_id, status, "
                    "mode, source_object_key, source_checksum) VALUES (:user_id, "
                    ":problem_id, :language_id, 'Pending', 'judge', 'private/source', "
                    ":checksum) RETURNING id"
                ),
                {
                    "user_id": user_id,
                    "problem_id": problem_id,
                    "language_id": language_id,
                    "checksum": "c" * 64,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO submission_case_results (submission_id, test_case_id, "
                    "status) VALUES (:submission_id, :test_case_id, 'Accepted')"
                ),
                {"submission_id": submission_id, "test_case_id": hidden_case_id},
            )
            event_id = uuid4()
            await connection.execute(
                text(
                    "INSERT INTO outbox_events (id, aggregate_type, aggregate_id, "
                    "event_type, payload) VALUES (:event_id, 'submission', "
                    ":submission_id, 'submission.created', CAST(:payload AS jsonb))"
                ),
                {
                    "event_id": event_id,
                    "submission_id": submission_id,
                    "payload": (
                        f'{{"submission_id":"{submission_id}",'
                        '"source_object_key":"private/source",'
                        '"docker_image":"must-not-survive"}'
                    ),
                },
            )
        return {
            "problem_id": problem_id,
            "hidden_case_id": hidden_case_id,
            "sample_case_id": sample_case_id,
            "submission_id": submission_id,
            "event_id": event_id,
        }
    finally:
        await engine.dispose()


async def _assert_migrated(database_url: str, seeded: dict[str, object]) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            sets = (
                await connection.execute(
                    text(
                        "SELECT id, version, status::text AS status, case_count, "
                        "total_score FROM test_sets WHERE problem_id = :problem_id "
                        "ORDER BY version"
                    ),
                    {"problem_id": seeded["problem_id"]},
                )
            ).mappings().all()
            assert [(row["version"], row["status"]) for row in sets] == [
                (1, "active"),
                (2, "inactive"),
            ]
            assert sets[0]["case_count"] == 1
            assert sets[0]["total_score"] == 100

            case_sets = dict(
                (
                    await connection.execute(
                        text(
                            "SELECT id, test_set_id FROM test_cases "
                            "WHERE id IN (:hidden_id, :sample_id)"
                        ),
                        {
                            "hidden_id": seeded["hidden_case_id"],
                            "sample_id": seeded["sample_case_id"],
                        },
                    )
                ).all()
            )
            assert case_sets[seeded["hidden_case_id"]] == sets[0]["id"]
            assert case_sets[seeded["sample_case_id"]] == sets[1]["id"]

            snapshot = (
                await connection.execute(
                    text(
                        "SELECT test_set_id, problem_version, time_limit_ms_snapshot, "
                        "memory_limit_mb_snapshot FROM submissions WHERE id = :id"
                    ),
                    {"id": seeded["submission_id"]},
                )
            ).mappings().one()
            assert snapshot == {
                "test_set_id": sets[0]["id"],
                "problem_version": 1,
                "time_limit_ms_snapshot": 2300,
                "memory_limit_mb_snapshot": 384,
            }
            case_result_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM submission_case_results "
                    "WHERE submission_id = :id AND test_case_id = :case_id"
                ),
                {
                    "id": seeded["submission_id"],
                    "case_id": seeded["hidden_case_id"],
                },
            )
            assert case_result_count == 1
            payload = await connection.scalar(
                text("SELECT payload FROM outbox_events WHERE id = :id"),
                {"id": seeded["event_id"]},
            )
            assert payload == {
                "event_id": str(seeded["event_id"]),
                "submission_id": str(seeded["submission_id"]),
            }
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_upgrade_from_0008_preserves_queued_submission_snapshot(
    postgres_database_url: str,
) -> None:
    base_url = make_url(postgres_database_url)
    database_name = f"upgrade_{uuid4().hex[:8]}_test"
    database_url = base_url.set(database=database_name).render_as_string(hide_password=False)
    asyncio.run(_create_database(postgres_database_url, database_name))
    try:
        config = make_alembic_config(database_url)
        command.upgrade(config, "20260811_0008")
        seeded = asyncio.run(_seed_legacy_schema(database_url))
        command.upgrade(config, "20260812_0009")
        asyncio.run(_assert_migrated(database_url, seeded))
    finally:
        asyncio.run(_drop_database(postgres_database_url, database_name))
