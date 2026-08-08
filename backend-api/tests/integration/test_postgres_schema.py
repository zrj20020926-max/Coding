from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.migration_bootstrap import (
    EXPECTED_ENUMS,
    EXPECTED_INDEXES,
    EXPECTED_TABLES,
    EXPECTED_TRIGGERS,
    SchemaState,
    inspect_schema,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migrations_preserve_postgresql_features(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "20260808_0004"

            auth_version = await connection.scalar(
                text(
                    "SELECT column_default FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'users' "
                    "AND column_name = 'auth_version'"
                )
            )
            assert auth_version == "1"

            tables = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tablename FROM pg_catalog.pg_tables "
                            "WHERE schemaname = 'public'"
                        )
                    )
                ).scalars()
            )
            assert EXPECTED_TABLES <= tables
            assert "outbox_events" in tables

            citext_columns = set(
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'users' "
                            "AND udt_name = 'citext'"
                        )
                    )
                ).scalars()
            )
            assert citext_columns == {"email", "username"}

            enum_names = set(
                (
                    await connection.execute(
                        text(
                            "SELECT typname FROM pg_catalog.pg_type "
                            "WHERE typtype = 'e' AND typnamespace = 'public'::regnamespace"
                        )
                    )
                ).scalars()
            )
            assert EXPECTED_ENUMS <= enum_names

            indexes = set(
                (
                    await connection.execute(
                        text(
                            "SELECT indexname FROM pg_catalog.pg_indexes "
                            "WHERE schemaname = 'public'"
                        )
                    )
                ).scalars()
            )
            assert EXPECTED_INDEXES <= indexes
            assert "idx_problems_public_created" in indexes
            assert "uq_submissions_user_idempotency_key" in indexes
            assert "idx_outbox_unpublished_retry" in indexes

            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_catalog.pg_trigger "
                            "WHERE NOT tgisinternal"
                        )
                    )
                ).scalars()
            )
            assert EXPECTED_TRIGGERS <= triggers
            assert "trg_submissions_status_transition" in triggers
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_citext_uniqueness_is_case_insensitive(postgres_database_url: str) -> None:
    engine = create_async_engine(postgres_database_url)
    suffix = uuid4().hex[:12]
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            await connection.execute(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname) "
                    "VALUES (:username, :email, :password_hash, :nickname)"
                ),
                {
                    "username": f"CaseUser_{suffix}",
                    "email": f"case-{suffix}@example.com",
                    "password_hash": "not-a-real-hash",
                    "nickname": "CITEXT test",
                },
            )
            with pytest.raises(IntegrityError):
                await connection.execute(
                    text(
                        "INSERT INTO users (username, email, password_hash, nickname) "
                        "VALUES (:username, :email, :password_hash, :nickname)"
                    ),
                    {
                        "username": f"caseuser_{suffix}",
                        "email": f"other-{suffix}@example.com",
                        "password_hash": "not-a-real-hash",
                        "nickname": "duplicate",
                    },
                )
            await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_rejects_skipped_submission_status_transition(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    suffix = uuid4().hex[:12]
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            user_id = await connection.scalar(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname) "
                    "VALUES (:username, :email, 'hash', 'transition test') RETURNING id"
                ),
                {
                    "username": f"transition_{suffix}",
                    "email": f"transition-{suffix}@example.com",
                },
            )
            problem_id = await connection.scalar(
                text(
                    "INSERT INTO problems (slug, title, description, difficulty, "
                    "input_description, output_description, visibility) "
                    "VALUES (:slug, 'transition', 'description', 'easy', 'input', "
                    "'output', 'public') RETURNING id"
                ),
                {"slug": f"transition-{suffix}"},
            )
            language_id = await connection.scalar(
                text("SELECT id FROM languages WHERE slug = 'python'")
            )
            submission_id = await connection.scalar(
                text(
                    "INSERT INTO submissions (user_id, problem_id, language_id, "
                    "source_object_key, source_checksum) VALUES (:user_id, :problem_id, "
                    ":language_id, 'internal', :checksum) RETURNING id"
                ),
                {
                    "user_id": user_id,
                    "problem_id": problem_id,
                    "language_id": language_id,
                    "checksum": "0" * 64,
                },
            )
            with pytest.raises(IntegrityError):
                await connection.execute(
                    text("UPDATE submissions SET status = 'Accepted' WHERE id = :id"),
                    {"id": submission_id},
                )
            await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_bootstrap_refuses_a_partial_schema(postgres_database_url: str) -> None:
    base_url = make_url(postgres_database_url)
    partial_database_name = f"partial_{uuid4().hex[:8]}_test"
    partial_url = base_url.set(database=partial_database_name).render_as_string(
        hide_password=False
    )
    admin_engine = create_async_engine(
        postgres_database_url,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'CREATE DATABASE "{partial_database_name}"'))

        partial_engine = create_async_engine(partial_url)
        try:
            async with partial_engine.begin() as connection:
                await connection.execute(text("CREATE TABLE users (id UUID PRIMARY KEY)"))
        finally:
            await partial_engine.dispose()

        inspection = await inspect_schema(partial_url)
        assert inspection.state is SchemaState.UNSAFE
        assert any(problem.startswith("missing tables:") for problem in inspection.problems)
    finally:
        async with admin_engine.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{partial_database_name}"'))
        await admin_engine.dispose()
