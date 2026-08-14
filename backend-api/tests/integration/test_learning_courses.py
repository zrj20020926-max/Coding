from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_rejects_exercise_prerequisite_cycles(
    postgres_database_url: str,
) -> None:
    engine = create_async_engine(postgres_database_url)
    suffix = uuid4().hex[:10]
    course_id: int | None = None
    problem_ids: list[int] = []
    try:
        async with engine.begin() as connection:
            for index in range(2):
                problem_id = await connection.scalar(
                    text(
                        "INSERT INTO problems (slug, title, description, difficulty, "
                        "input_description, output_description, visibility) VALUES "
                        "(:slug, :title, 'd', 'easy', 'stdin', 'stdout', 'public') "
                        "RETURNING id"
                    ),
                    {
                        "slug": f"cycle-problem-{suffix}-{index}",
                        "title": f"cycle {index}",
                    },
                )
                problem_ids.append(problem_id)
            course_id = await connection.scalar(
                text(
                    "INSERT INTO courses (slug, title, description, type, sort_order, "
                    "is_public) VALUES (:slug, 'cycle', 'cycle', 'input', 9999, false) "
                    "RETURNING id"
                ),
                {"slug": f"cycle-course-{suffix}"},
            )
            chapter_id = await connection.scalar(
                text(
                    "INSERT INTO chapters (course_id, slug, title, description, sort_order, "
                    "estimated_minutes, is_public) VALUES (:course_id, :slug, 'cycle', "
                    "'cycle', 1, 10, false) RETURNING id"
                ),
                {"course_id": course_id, "slug": f"cycle-chapter-{suffix}"},
            )
            exercise_ids = []
            for index, problem_id in enumerate(problem_ids, start=1):
                exercise_ids.append(
                    await connection.scalar(
                        text(
                            "INSERT INTO exercises (problem_id, chapter_id, sort_order, "
                            "learning_objectives, v8_notes, nodejs_notes, common_mistakes, "
                            "starter_code_v8, starter_code_nodejs, estimated_minutes) VALUES "
                            "(:problem_id, :chapter_id, :sort_order, 'learn', 'v8', 'node', "
                            "'[]'::jsonb, 'print(1)', 'console.log(1)', 5) RETURNING id"
                        ),
                        {
                            "problem_id": problem_id,
                            "chapter_id": chapter_id,
                            "sort_order": index,
                        },
                    )
                )
            await connection.execute(
                text(
                    "INSERT INTO exercise_prerequisites (exercise_id, prerequisite_id) "
                    "VALUES (:exercise_id, :prerequisite_id)"
                ),
                {"exercise_id": exercise_ids[1], "prerequisite_id": exercise_ids[0]},
            )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            "INSERT INTO exercise_prerequisites "
                            "(exercise_id, prerequisite_id) VALUES "
                            "(:exercise_id, :prerequisite_id)"
                        ),
                        {
                            "exercise_id": exercise_ids[0],
                            "prerequisite_id": exercise_ids[1],
                        },
                    )
    finally:
        async with engine.begin() as connection:
            if course_id is not None:
                await connection.execute(
                    text(
                        "DELETE FROM exercise_prerequisites WHERE exercise_id IN "
                        "(SELECT e.id FROM exercises e JOIN chapters c ON c.id=e.chapter_id "
                        "WHERE c.course_id=:course_id)"
                    ),
                    {"course_id": course_id},
                )
                await connection.execute(
                    text(
                        "DELETE FROM exercises WHERE chapter_id IN "
                        "(SELECT id FROM chapters WHERE course_id=:course_id)"
                    ),
                    {"course_id": course_id},
                )
                await connection.execute(
                    text("DELETE FROM courses WHERE id=:course_id"),
                    {"course_id": course_id},
                )
            if problem_ids:
                await connection.execute(
                    text("DELETE FROM problems WHERE id = ANY(:ids)"),
                    {"ids": problem_ids},
                )
        await engine.dispose()
