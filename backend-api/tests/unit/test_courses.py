from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import (
    Chapter,
    Course,
    CourseType,
    Exercise,
    ExercisePrerequisite,
    ExerciseProgressStatus,
    UserExerciseProgress,
)
from app.models.problem import (
    Language,
    Problem,
    ProblemDifficulty,
    ProblemVisibility,
    TrainingCategory,
)
from app.models.user import User


async def register(client: AsyncClient, username: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "safe-password-123",
            "nickname": username,
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def problem(slug: str, visibility: ProblemVisibility = ProblemVisibility.PUBLIC) -> Problem:
    return Problem(
        slug=slug,
        title=slug,
        description="public statement",
        difficulty=ProblemDifficulty.EASY,
        training_category=TrainingCategory.SINGLE_VALUE,
        input_description="stdin",
        output_description="stdout",
        data_constraints="small",
        sample_input="1\n",
        sample_output="1\n",
        sample_explanation="echo",
        visibility=visibility,
    )


def exercise(item: Problem, order: int) -> Exercise:
    return Exercise(
        problem=item,
        sort_order=order,
        learning_objectives="learn stdout",
        v8_notes="use readline and print",
        nodejs_notes="use fs and stdout",
        common_mistakes=["debug output"],
        starter_code_v8="print(readline());",
        starter_code_nodejs="process.stdout.write('');",
        estimated_minutes=8,
        is_public=True,
        prerequisite_links=[],
    )


async def seed_courses(db: AsyncSession) -> tuple[Exercise, Exercise]:
    first_problem = problem("course-first")
    second_problem = problem("course-second")
    hidden_problem = problem("hidden-exercise")
    offline_problem = problem("offline-exercise", ProblemVisibility.PRIVATE)
    first = exercise(first_problem, 1)
    second = exercise(second_problem, 1)
    hidden = exercise(hidden_problem, 1)
    offline = exercise(offline_problem, 2)
    chapter_later = Chapter(
        slug="chapter-later",
        title="Later",
        description="later chapter",
        sort_order=2,
        estimated_minutes=8,
        is_public=True,
        exercises=[second],
    )
    chapter_first = Chapter(
        slug="chapter-first",
        title="First",
        description="first chapter",
        sort_order=1,
        estimated_minutes=8,
        is_public=True,
        exercises=[first],
    )
    hidden_chapter = Chapter(
        slug="hidden-chapter",
        title="Hidden",
        description="private chapter",
        sort_order=3,
        estimated_minutes=16,
        is_public=False,
        exercises=[hidden, offline],
    )
    public_course = Course(
        slug="public-course",
        title="Public course",
        description="course",
        type=CourseType.INPUT,
        sort_order=2,
        is_public=True,
        chapters=[chapter_later, chapter_first, hidden_chapter],
    )
    private_course = Course(
        slug="private-course",
        title="Private course",
        description="private",
        type=CourseType.MIXED,
        sort_order=1,
        is_public=False,
        chapters=[
            Chapter(
                slug="private-course-chapter",
                title="Private",
                description="private",
                sort_order=1,
                estimated_minutes=8,
                is_public=True,
                exercises=[exercise(problem("private-course-exercise"), 1)],
            )
        ],
    )
    db.add_all(
        [
            public_course,
            private_course,
            Language(
                slug="javascript-v8",
                display_name="JavaScript V8",
                version="ES2023",
                monaco_language="javascript",
                source_filename="main.js",
                run_command="internal",
                docker_image="internal",
                enabled=True,
            ),
            Language(
                slug="nodejs",
                display_name="Node.js",
                version="22",
                monaco_language="javascript",
                source_filename="main.js",
                run_command="internal",
                docker_image="internal",
                enabled=True,
            ),
        ]
    )
    await db.flush()
    second.prerequisite_links = [ExercisePrerequisite(prerequisite_id=first.id)]
    await db.commit()
    return first, second


@pytest.mark.unit
@pytest.mark.asyncio
async def test_public_courses_are_sorted_and_hide_private_content(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_courses(db_session)
    courses = await client.get("/api/v1/courses")
    assert courses.status_code == 200
    assert [item["slug"] for item in courses.json()] == ["public-course"]
    assert courses.json()[0]["progress"]["authenticated"] is False

    detail = await client.get("/api/v1/courses/public-course")
    body = detail.json()
    assert detail.status_code == 200
    assert [item["slug"] for item in body["chapters"]] == [
        "chapter-first",
        "chapter-later",
    ]
    assert body["exercise_count"] == 2
    assert body["next_exercise"]["slug"] == "course-first"
    assert "progress" not in body["chapters"][0]["exercises"][0]
    assert (await client.get("/api/v1/courses/private-course")).status_code == 404
    assert (await client.get("/api/v1/chapters/hidden-chapter")).status_code == 404
    assert (await client.get("/api/v1/exercises/offline-exercise")).status_code == 404


@pytest.mark.unit
@pytest.mark.asyncio
async def test_runtime_progress_and_prerequisite_recommendation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first, second = await seed_courses(db_session)
    headers = await register(client, "course_progress_user")
    user = await db_session.scalar(
        select(User).where(User.username == "course_progress_user")
    )
    assert user is not None
    completed_at = datetime.now(timezone.utc)
    db_session.add(
        UserExerciseProgress(
            user_id=user.id,
            exercise_id=first.id,
            status=ExerciseProgressStatus.COMPLETED,
            selected_runtime="javascript-v8",
            attempt_count=2,
            v8_attempt_count=1,
            nodejs_attempt_count=1,
            v8_completed_at=completed_at,
            first_completed_at=completed_at,
            last_attempted_at=completed_at,
        )
    )
    await db_session.commit()

    detail = await client.get("/api/v1/courses/public-course", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["progress"] == {
        "authenticated": True,
        "completed_count": 1,
        "both_runtimes_completed_count": 0,
        "v8_completed_count": 1,
        "nodejs_completed_count": 0,
        "attempted_count": 1,
        "total_count": 2,
        "completion_ratio": 0.5,
        "both_runtimes_completion_ratio": 0.0,
    }
    assert body["next_exercise"]["id"] == second.id
    recommendation = await client.get(
        "/api/v1/users/me/recommended-exercise", headers=headers
    )
    assert recommendation.json()["exercise"]["slug"] == "course-second"
    dashboard = await client.get("/api/v1/users/me/learning-progress", headers=headers)
    assert dashboard.json()["progress"]["v8_completed_count"] == 1
    assert dashboard.json()["progress"]["nodejs_completed_count"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_exercise_public_dto_does_not_leak_judge_material(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_courses(db_session)
    response = await client.get("/api/v1/exercises/course-first")
    assert response.status_code == 200
    serialized = response.text
    for forbidden in (
        "reference_solutions",
        "test_cases",
        "test_set",
        "object_key",
        "checksum",
        "docker_image",
        "compile_command",
        "run_command",
    ):
        assert forbidden not in serialized


@pytest.mark.unit
@pytest.mark.asyncio
async def test_private_learning_endpoints_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/users/me/learning-progress")).status_code == 401
    assert (
        await client.get("/api/v1/users/me/recommended-exercise")
    ).status_code == 401
