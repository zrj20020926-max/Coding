import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.migration_bootstrap import (
    EXPECTED_ENUMS,
    EXPECTED_INDEXES,
    EXPECTED_TABLES,
    EXPECTED_TRIGGERS,
    SchemaState,
    inspect_schema,
)
from app.maintenance.rebuild_statistics import rebuild_statistics
from app.models.content import ContentReviewStatus
from app.models.user import User
from app.services.discussions import create_report, moderate_comment


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migrations_preserve_postgresql_features(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "20260813_0013"

            problem_columns = set(
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'problems'"
                        )
                    )
                ).scalars()
            )
            assert "training_category" in problem_columns

            enabled_languages = set(
                (
                    await connection.execute(
                        text("SELECT slug FROM languages WHERE enabled IS TRUE")
                    )
                ).scalars()
            )
            assert enabled_languages == {"javascript-v8", "nodejs"}

            submission_columns = set(
                (
                    await connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'public' AND table_name = 'submissions'"
                        )
                    )
                ).scalars()
            )
            assert {
                "mode",
                "sample_output",
                "test_set_id",
                "problem_version",
                "time_limit_ms_snapshot",
                "memory_limit_mb_snapshot",
            } <= submission_columns

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
            assert "submission_stat_events" in tables
            assert "content_reports" in tables
            assert "content_moderation_actions" in tables
            assert "ai_usage_records" in tables
            assert "audit_logs" in tables
            assert "test_sets" in tables

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
            assert "submission_mode" in enum_names
            assert "content_review_status" in enum_names
            assert {"test_set_status", "checker_type"} <= enum_names
            assert "training_category" in enum_names

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
            assert (EXPECTED_INDEXES - {"idx_test_cases_problem"}) <= indexes
            assert "idx_problems_public_created" in indexes
            assert "uq_submissions_user_idempotency_key" in indexes
            assert "idx_outbox_unpublished_retry" in indexes
            assert "idx_submissions_user_mode_created" in indexes
            assert "idx_stat_events_user_applied" in indexes
            assert "idx_stat_events_problem_applied" in indexes
            assert "idx_favorites_user_created" in indexes
            assert "idx_favorites_problem" in indexes
            assert "idx_collections_public_created" in indexes
            assert "idx_discussions_public_order" in indexes
            assert "uq_reports_user_discussion" in indexes
            assert "idx_ai_analyses_completed_fingerprint" in indexes
            assert "idx_ai_usage_user_created" in indexes
            assert "uq_test_sets_active_problem" in indexes
            assert "idx_test_cases_test_set_sequence" in indexes
            assert "idx_problems_public_training_category" in indexes

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
            assert {
                "trg_test_sets_protect",
                "trg_test_cases_protect",
                "trg_submissions_snapshot_immutable",
                "trg_problems_version",
            } <= triggers
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
                    "mode, source_object_key, source_checksum, problem_version, "
                    "time_limit_ms_snapshot, memory_limit_mb_snapshot) VALUES "
                    "(:user_id, :problem_id, :language_id, 'sample', 'internal', "
                    ":checksum, 1, 1000, 256) RETURNING id"
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
async def test_statistics_rebuild_is_repeatable(postgres_database_url: str) -> None:
    engine = create_async_engine(postgres_database_url)
    suffix = uuid4().hex[:12]
    user_id = None
    problem_id = None
    try:
        async with engine.begin() as connection:
            user_id = await connection.scalar(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname, "
                    "solved_count, submission_count, accepted_count) VALUES "
                    "(:username, :email, 'hash', 'rebuild', 99, 99, 99) RETURNING id"
                ),
                {
                    "username": f"rebuild_{suffix}",
                    "email": f"rebuild-{suffix}@example.com",
                },
            )
            problem_id = await connection.scalar(
                text(
                    "INSERT INTO problems (slug, title, description, difficulty, "
                    "input_description, output_description, visibility, submission_count, "
                    "accepted_count) VALUES (:slug, 'rebuild', 'description', 'medium', "
                    "'input', 'output', 'public', 99, 99) RETURNING id"
                ),
                {"slug": f"rebuild-{suffix}"},
            )
            language_id = await connection.scalar(
                text("SELECT id FROM languages WHERE slug = 'python'")
            )
            test_set_id = await connection.scalar(
                text(
                    "INSERT INTO test_sets (problem_id, version, status, case_count, "
                    "total_score) VALUES (:problem_id, 1, 'active', 1, 100) RETURNING id"
                ),
                {"problem_id": problem_id},
            )
            for index, status in enumerate(("Accepted", "Wrong Answer"), start=1):
                await connection.execute(
                    text(
                        "INSERT INTO submissions (user_id, problem_id, language_id, "
                        "status, mode, source_object_key, source_checksum, judged_at, "
                        "test_set_id, problem_version, time_limit_ms_snapshot, "
                        "memory_limit_mb_snapshot) "
                        "VALUES (:user_id, :problem_id, :language_id, "
                        "CAST(:status AS submission_status), 'judge', :object_key, "
                        ":checksum, now(), :test_set_id, 1, 1000, 256)"
                    ),
                    {
                        "user_id": user_id,
                        "problem_id": problem_id,
                        "language_id": language_id,
                        "status": status,
                        "object_key": f"internal/rebuild/{index}",
                        "checksum": str(index) * 64,
                        "test_set_id": test_set_id,
                    },
                )

        first = await rebuild_statistics(postgres_database_url)
        second = await rebuild_statistics(postgres_database_url)
        assert first.progress_rows >= 1
        assert second == first

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
                        "SELECT solved_count, submission_count, accepted_count "
                        "FROM users WHERE id = :user_id"
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
            "solved_count": 1,
            "submission_count": 2,
            "accepted_count": 1,
        }
        assert problem_stats == {"submission_count": 2, "accepted_count": 1}
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
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_duplicate_report_increments_count_once(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex[:12]
    reporter_id: UUID | None = None
    author_id: UUID | None = None
    problem_id: int | None = None
    discussion_id: int | None = None
    try:
        async with engine.begin() as connection:
            author_id = await connection.scalar(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname) "
                    "VALUES (:username, :email, 'hash', 'author') RETURNING id"
                ),
                {
                    "username": f"report_author_{suffix}",
                    "email": f"report-author-{suffix}@example.com",
                },
            )
            reporter_id = await connection.scalar(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname) "
                    "VALUES (:username, :email, 'hash', 'reporter') RETURNING id"
                ),
                {
                    "username": f"report_user_{suffix}",
                    "email": f"report-user-{suffix}@example.com",
                },
            )
            problem_id = await connection.scalar(
                text(
                    "INSERT INTO problems (slug, title, description, difficulty, "
                    "input_description, output_description, visibility) VALUES "
                    "(:slug, 'report', 'd', 'easy', 'i', 'o', 'public') RETURNING id"
                ),
                {"slug": f"report-{suffix}"},
            )
            discussion_id = await connection.scalar(
                text(
                    "INSERT INTO discussions (problem_id, user_id, title, content) "
                    "VALUES (:problem_id, :user_id, 'report', 'content') RETURNING id"
                ),
                {"problem_id": problem_id, "user_id": author_id},
            )

        assert reporter_id is not None and discussion_id is not None

        async def submit_report() -> bool:
            async with session_factory() as session:
                state = await create_report(
                    session,
                    reporter_id,
                    "concurrent duplicate",
                    discussion_id=discussion_id,
                )
                return state.created

        results = await asyncio.gather(submit_report(), submit_report())
        assert sorted(results) == [False, True]

        async with engine.connect() as connection:
            report_count = await connection.scalar(
                text("SELECT report_count FROM discussions WHERE id = :id"),
                {"id": discussion_id},
            )
            rows = await connection.scalar(
                text("SELECT count(*) FROM content_reports WHERE discussion_id = :id"),
                {"id": discussion_id},
            )
        assert report_count == 1
        assert rows == 1
    finally:
        async with engine.begin() as connection:
            if discussion_id is not None:
                await connection.execute(
                    text("DELETE FROM discussions WHERE id = :id"),
                    {"id": discussion_id},
                )
            if problem_id is not None:
                await connection.execute(
                    text("DELETE FROM problems WHERE id = :id"),
                    {"id": problem_id},
                )
            for user_id in (reporter_id, author_id):
                if user_id is not None:
                    await connection.execute(
                        text("DELETE FROM users WHERE id = :id"),
                        {"id": user_id},
                    )
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_comment_approval_increments_count_once(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    suffix = uuid4().hex[:12]
    admin_id: UUID | None = None
    author_id: UUID | None = None
    problem_id: int | None = None
    discussion_id: int | None = None
    comment_id: int | None = None
    try:
        async with engine.begin() as connection:
            admin_id = await connection.scalar(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname, is_admin) "
                    "VALUES (:username, :email, 'hash', 'admin', true) RETURNING id"
                ),
                {
                    "username": f"moderation_admin_{suffix}",
                    "email": f"moderation-admin-{suffix}@example.com",
                },
            )
            author_id = await connection.scalar(
                text(
                    "INSERT INTO users (username, email, password_hash, nickname) "
                    "VALUES (:username, :email, 'hash', 'author') RETURNING id"
                ),
                {
                    "username": f"moderation_author_{suffix}",
                    "email": f"moderation-author-{suffix}@example.com",
                },
            )
            problem_id = await connection.scalar(
                text(
                    "INSERT INTO problems (slug, title, description, difficulty, "
                    "input_description, output_description, visibility) VALUES "
                    "(:slug, 'moderation', 'd', 'easy', 'i', 'o', 'public') RETURNING id"
                ),
                {"slug": f"moderation-{suffix}"},
            )
            discussion_id = await connection.scalar(
                text(
                    "INSERT INTO discussions (problem_id, user_id, title, content) "
                    "VALUES (:problem_id, :user_id, 'moderation', 'content') RETURNING id"
                ),
                {"problem_id": problem_id, "user_id": author_id},
            )
            comment_id = await connection.scalar(
                text(
                    "INSERT INTO discussion_comments "
                    "(discussion_id, user_id, content, review_status) "
                    "VALUES (:discussion_id, :user_id, 'pending', 'pending') RETURNING id"
                ),
                {"discussion_id": discussion_id, "user_id": author_id},
            )

        assert admin_id is not None and comment_id is not None

        async def approve_comment() -> None:
            async with session_factory() as session:
                admin = await session.scalar(select(User).where(User.id == admin_id))
                assert admin is not None
                await moderate_comment(
                    session,
                    comment_id,
                    admin,
                    ContentReviewStatus.APPROVED,
                    "concurrent approval",
                )

        await asyncio.gather(approve_comment(), approve_comment())

        async with engine.connect() as connection:
            comment_count = await connection.scalar(
                text("SELECT comment_count FROM discussions WHERE id = :id"),
                {"id": discussion_id},
            )
        assert comment_count == 1
    finally:
        async with engine.begin() as connection:
            if comment_id is not None:
                await connection.execute(
                    text(
                        "DELETE FROM content_moderation_actions "
                        "WHERE target_type = 'comment' AND target_id = :id"
                    ),
                    {"id": comment_id},
                )
            if discussion_id is not None:
                await connection.execute(
                    text("DELETE FROM discussions WHERE id = :id"),
                    {"id": discussion_id},
                )
            if problem_id is not None:
                await connection.execute(
                    text("DELETE FROM problems WHERE id = :id"),
                    {"id": problem_id},
                )
            for user_id in (admin_id, author_id):
                if user_id is not None:
                    await connection.execute(
                        text("DELETE FROM users WHERE id = :id"),
                        {"id": user_id},
                    )
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
