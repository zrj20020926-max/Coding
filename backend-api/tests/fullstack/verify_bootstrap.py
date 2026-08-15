from __future__ import annotations

import asyncio
import json
import os
import urllib.request

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def get_json(path: str) -> dict[str, object] | list[object]:
    base_url = os.environ["FULL_STACK_API_URL"].rstrip("/")
    with urllib.request.urlopen(f"{base_url}{path}", timeout=30) as response:
        return json.loads(response.read())


async def verify_database() -> dict[str, int]:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != "20260815_0018":
                raise RuntimeError("database is not migrated to the expected Alembic head")

            public_count = int(
                await connection.scalar(
                    text("SELECT count(*) FROM problems WHERE visibility = 'public'")
                )
                or 0
            )
            input_count = int(
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM problems WHERE visibility = 'public' "
                        "AND slug LIKE 'js-acm-%' AND slug NOT LIKE 'js-acm-output-%'"
                    )
                )
                or 0
            )
            output_count = int(
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM problems WHERE visibility = 'public' "
                        "AND slug LIKE 'js-acm-output-%'"
                    )
                )
                or 0
            )
            missing_active_sets = int(
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM problems p WHERE p.visibility = 'public' "
                        "AND NOT EXISTS (SELECT 1 FROM test_sets ts "
                        "WHERE ts.problem_id = p.id AND ts.status = 'active' "
                        "AND EXISTS (SELECT 1 FROM test_cases tc WHERE tc.test_set_id = ts.id))"
                    )
                )
                or 0
            )
            missing_starters = int(
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM exercises e "
                        "JOIN chapters ch ON ch.id = e.chapter_id "
                        "JOIN courses c ON c.id = ch.course_id "
                        "JOIN problems p ON p.id = e.problem_id "
                        "WHERE c.is_public AND ch.is_public AND p.visibility = 'public' "
                        "AND (length(trim(e.starter_code_v8)) = 0 "
                        "OR length(trim(e.starter_code_nodejs)) = 0)"
                    )
                )
                or 0
            )

            expected_courses = {
                "javascript-v8-quickstart",
                "stdout-formats",
                "comprehensive-io-training",
            }
            course_slugs = set(
                (
                    await connection.execute(
                        text("SELECT slug FROM courses WHERE is_public")
                    )
                ).scalars()
            )

        if input_count < 80 or output_count < 40 or public_count < 120:
            raise RuntimeError("content bootstrap did not import the required training volume")
        if missing_active_sets:
            raise RuntimeError("a public exercise is missing an active hidden test set")
        if missing_starters:
            raise RuntimeError("a public exercise is missing a V8 or Node.js starter template")
        if not expected_courses <= course_slugs:
            raise RuntimeError("input, output, or comprehensive course is missing")
        return {
            "public_exercises": public_count,
            "input_exercises": input_count,
            "output_exercises": output_count,
        }
    finally:
        await engine.dispose()


def verify_public_api(expected_count: int) -> None:
    first = get_json("/problems?page=1&page_size=100&sort=oldest")
    if not isinstance(first, dict):
        raise RuntimeError("problem page response is invalid")
    items = list(first.get("items", []))
    for page in range(2, int(first.get("pages", 1)) + 1):
        payload = get_json(f"/problems?page={page}&page_size=100&sort=oldest")
        if not isinstance(payload, dict):
            raise RuntimeError("problem page response is invalid")
        items.extend(payload.get("items", []))
    if len(items) != expected_count:
        raise RuntimeError("public API count differs from the migrated database")

    forbidden = {
        "test_sets",
        "test_cases",
        "input_object_key",
        "output_object_key",
        "checksum",
        "reference_solution",
        "docker_image",
        "compile_command",
    }
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("problem item response is invalid")
        detail = get_json(f"/problems/{item['slug']}")
        if not isinstance(detail, dict):
            raise RuntimeError("problem detail response is invalid")
        if not detail.get("starter_code_v8") or not detail.get("starter_code_nodejs"):
            raise RuntimeError("public exercise is missing starter templates")
        if forbidden.intersection(detail):
            raise RuntimeError("public exercise DTO exposes an internal field")


async def main() -> None:
    counts = await verify_database()
    verify_public_api(counts["public_exercises"])
    print(json.dumps({"status": "ok", **counts}, separators=(",", ":")))


if __name__ == "__main__":
    asyncio.run(main())
