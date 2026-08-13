"""Safely adopt legacy databases and apply Alembic migrations."""

import argparse
import asyncio
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

INITIAL_REVISION = "20260808_0001"
PROJECT_DIR = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    "ai_analyses",
    "collection_problems",
    "collections",
    "daily_challenges",
    "discussion_comments",
    "discussions",
    "favorites",
    "languages",
    "problem_tags",
    "problems",
    "submission_case_results",
    "submissions",
    "tags",
    "test_cases",
    "user_problem_progress",
    "users",
}
EXPECTED_ENUMS = {
    "ai_analysis_status",
    "problem_difficulty",
    "problem_visibility",
    "submission_status",
}
EXPECTED_INDEXES = {
    "idx_comments_discussion_created",
    "idx_discussions_problem_created",
    "idx_problem_tags_tag_id",
    "idx_problems_public_difficulty",
    "idx_progress_user_accepted",
    "idx_submissions_pending",
    "idx_submissions_problem_status",
    "idx_submissions_queue_message",
    "idx_submissions_user_created",
    "idx_test_cases_problem",
}
EXPECTED_TRIGGERS = {
    "trg_ai_analyses_updated_at",
    "trg_collections_updated_at",
    "trg_comments_updated_at",
    "trg_discussions_updated_at",
    "trg_languages_updated_at",
    "trg_problems_updated_at",
    "trg_progress_updated_at",
    "trg_submissions_updated_at",
    "trg_users_updated_at",
}
# Legacy SQL installations are stamped at the initial revision before later migrations
# rename `javascript` to `nodejs` and add the V8 compatibility mode.
EXPECTED_LANGUAGES = {"cpp", "go", "java", "javascript", "python"}
EXPECTED_TAGS = {
    "array",
    "bfs",
    "binary-tree",
    "dfs",
    "dynamic-programming",
    "graph",
    "greedy",
    "linked-list",
    "sliding-window",
    "union-find",
}


class SchemaState(str, Enum):
    EMPTY = "empty"
    LEGACY = "legacy"
    VERSIONED = "versioned"
    UNSAFE = "unsafe"


@dataclass(frozen=True)
class SchemaInspection:
    state: SchemaState
    problems: tuple[str, ...] = ()


def make_alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


async def inspect_schema(database_url: str) -> SchemaInspection:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            table_names = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tablename FROM pg_catalog.pg_tables "
                            "WHERE schemaname = 'public'"
                        )
                    )
                ).scalars()
            )
            if "alembic_version" in table_names:
                return SchemaInspection(SchemaState.VERSIONED)

            present_domain_tables = table_names & EXPECTED_TABLES
            if not present_domain_tables:
                return SchemaInspection(SchemaState.EMPTY)

            problems: list[str] = []
            missing_tables = EXPECTED_TABLES - table_names
            if missing_tables:
                problems.append("missing tables: " + ", ".join(sorted(missing_tables)))

            extensions = set(
                (
                    await connection.execute(
                        text("SELECT extname FROM pg_catalog.pg_extension")
                    )
                ).scalars()
            )
            missing_extensions = {"citext", "pgcrypto"} - extensions
            if missing_extensions:
                problems.append("missing extensions: " + ", ".join(sorted(missing_extensions)))

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
            missing_enums = EXPECTED_ENUMS - enum_names
            if missing_enums:
                problems.append("missing enums: " + ", ".join(sorted(missing_enums)))

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
            if citext_columns != {"email", "username"}:
                problems.append("users.username and users.email must both use CITEXT")

            index_names = set(
                (
                    await connection.execute(
                        text(
                            "SELECT indexname FROM pg_catalog.pg_indexes "
                            "WHERE schemaname = 'public'"
                        )
                    )
                ).scalars()
            )
            missing_indexes = EXPECTED_INDEXES - index_names
            if missing_indexes:
                problems.append("missing indexes: " + ", ".join(sorted(missing_indexes)))

            trigger_names = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_catalog.pg_trigger "
                            "WHERE NOT tgisinternal"
                        )
                    )
                ).scalars()
            )
            missing_triggers = EXPECTED_TRIGGERS - trigger_names
            if missing_triggers:
                problems.append("missing triggers: " + ", ".join(sorted(missing_triggers)))

            if {"languages", "tags"} <= table_names:
                language_slugs = set(
                    (await connection.execute(text("SELECT slug FROM languages"))).scalars()
                )
                tag_slugs = set((await connection.execute(text("SELECT slug FROM tags"))).scalars())
                if not EXPECTED_LANGUAGES <= language_slugs:
                    problems.append("language seed data is incomplete")
                if not EXPECTED_TAGS <= tag_slugs:
                    problems.append("tag seed data is incomplete")

            if problems:
                return SchemaInspection(SchemaState.UNSAFE, tuple(problems))
            return SchemaInspection(SchemaState.LEGACY)
    finally:
        await engine.dispose()


def migrate(database_url: str, check_only: bool = False) -> SchemaInspection:
    inspection = asyncio.run(inspect_schema(database_url))
    if inspection.state is SchemaState.UNSAFE:
        details = "\n- ".join(inspection.problems)
        raise RuntimeError(
            "Refusing to stamp an unrecognized or incomplete database:\n- " + details
        )
    if check_only:
        return inspection

    config = make_alembic_config(database_url)
    if inspection.state is SchemaState.LEGACY:
        command.stamp(config, INITIAL_REVISION)
    command.upgrade(config, "head")
    return inspection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate, adopt, and migrate the ACM platform PostgreSQL schema."
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_url: str = args.database_url or settings.database_url
    inspection = migrate(database_url, check_only=args.check_only)
    action = "checked" if args.check_only else "migrated"
    print(f"Database {action}; detected initial state: {inspection.state.value}")


if __name__ == "__main__":
    main()
