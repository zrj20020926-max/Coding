from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.problem import (
    Favorite,
    Language,
    Problem,
    ProblemDifficulty,
    ProblemTag,
    ProblemVisibility,
    Tag,
    UserProblemProgress,
)
from app.models.submission import Submission, SubmissionMode, SubmissionStatus
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


async def seed_training_catalog(
    db: AsyncSession,
) -> tuple[Problem, Problem, Problem, Language]:
    array = Tag(slug="array", name="数组")
    dp = Tag(slug="dynamic-programming", name="动态规划")
    easy = Problem(
        slug="training-sum",
        title="训练求和",
        description="description",
        difficulty=ProblemDifficulty.EASY,
        input_description="input",
        output_description="output",
        visibility=ProblemVisibility.PUBLIC,
        tag_links=[ProblemTag(tag=array)],
    )
    hard = Problem(
        slug="training-dp",
        title="训练动态规划",
        description="description",
        difficulty=ProblemDifficulty.HARD,
        input_description="input",
        output_description="output",
        visibility=ProblemVisibility.PUBLIC,
        tag_links=[ProblemTag(tag=dp)],
    )
    private = Problem(
        slug="training-private",
        title="内部题目",
        description="description",
        difficulty=ProblemDifficulty.MEDIUM,
        input_description="input",
        output_description="output",
        visibility=ProblemVisibility.PRIVATE,
    )
    language = Language(
        slug="python",
        display_name="Python",
        version="3.12",
        monaco_language="python",
        source_filename="main.py",
        compile_command=None,
        run_command="python -I main.py",
        docker_image="private/python:3.12",
        enabled=True,
        sort_order=10,
    )
    db.add_all([easy, hard, private, language])
    await db.commit()
    return easy, hard, private, language


@pytest.mark.unit
@pytest.mark.asyncio
async def test_favorites_are_idempotent_and_owned(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    easy, hard, private, _ = await seed_training_catalog(db_session)
    alice_headers = await register(client, "favorite_alice")
    bob_headers = await register(client, "favorite_bob")

    first = await client.post(
        f"/api/v1/problems/{easy.id}/favorite", headers=alice_headers
    )
    duplicate = await client.post(
        f"/api/v1/problems/{easy.id}/favorite", headers=alice_headers
    )
    await client.post(f"/api/v1/problems/{hard.id}/favorite", headers=bob_headers)

    assert first.status_code == 200
    assert duplicate.json() == {"problem_id": easy.id, "favorited": True}
    alice_favorites = await client.get("/api/v1/favorites", headers=alice_headers)
    assert [item["slug"] for item in alice_favorites.json()["items"]] == [
        "training-sum"
    ]

    # Removing a problem that belongs only to another user's favorites is a no-op.
    removed = await client.delete(
        f"/api/v1/problems/{hard.id}/favorite", headers=alice_headers
    )
    assert removed.json() == {"problem_id": hard.id, "favorited": False}
    bob_favorites = await client.get("/api/v1/favorites", headers=bob_headers)
    assert [item["slug"] for item in bob_favorites.json()["items"]] == ["training-dp"]

    hidden = await client.post(
        f"/api/v1/problems/{private.id}/favorite", headers=alice_headers
    )
    assert hidden.status_code == 404
    assert hidden.json()["detail"]["code"] == "PROBLEM_NOT_FOUND"

    alice = await db_session.scalar(
        select(User).where(User.username == "favorite_alice")
    )
    assert alice is not None
    favorite_count = await db_session.scalar(
        select(func.count(Favorite.problem_id)).where(Favorite.user_id == alice.id)
    )
    assert favorite_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_training_dashboard_is_scoped_to_current_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    easy, hard, _, language = await seed_training_catalog(db_session)
    alice_headers = await register(client, "training_alice")
    await register(client, "training_bob")
    alice = await db_session.scalar(select(User).where(User.username == "training_alice"))
    bob = await db_session.scalar(select(User).where(User.username == "training_bob"))
    assert alice is not None and bob is not None

    accepted_at = datetime.now(timezone.utc)
    alice.solved_count = 1
    alice.submission_count = 2
    alice.accepted_count = 1
    db_session.add_all(
        [
            UserProblemProgress(
                user_id=alice.id,
                problem_id=easy.id,
                attempt_count=1,
                accepted=True,
                first_accepted_at=accepted_at,
            ),
            UserProblemProgress(
                user_id=alice.id,
                problem_id=hard.id,
                attempt_count=1,
                accepted=False,
            ),
            UserProblemProgress(
                user_id=bob.id,
                problem_id=hard.id,
                attempt_count=1,
                accepted=True,
                first_accepted_at=accepted_at,
            ),
            Submission(
                user_id=alice.id,
                problem_id=easy.id,
                language_id=language.id,
                status=SubmissionStatus.ACCEPTED,
                mode=SubmissionMode.JUDGE,
                source_object_key="internal/alice/accepted",
                source_checksum="1" * 64,
                judged_at=accepted_at,
            ),
            Submission(
                user_id=alice.id,
                problem_id=hard.id,
                language_id=language.id,
                status=SubmissionStatus.WRONG_ANSWER,
                mode=SubmissionMode.JUDGE,
                source_object_key="internal/alice/wrong",
                source_checksum="2" * 64,
                judged_at=accepted_at,
            ),
            Submission(
                user_id=bob.id,
                problem_id=hard.id,
                language_id=language.id,
                status=SubmissionStatus.ACCEPTED,
                mode=SubmissionMode.JUDGE,
                source_object_key="internal/bob/accepted",
                source_checksum="3" * 64,
                judged_at=accepted_at,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/users/me/training", headers=alice_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["counters"] == {
        "solved_count": 1,
        "submission_count": 2,
        "accepted_count": 1,
    }
    assert len(body["recent_submissions"]) == 2
    assert {item["problem"]["slug"] for item in body["recent_submissions"]} == {
        "training-sum",
        "training-dp",
    }
    assert [item["slug"] for item in body["solved_problems"]] == ["training-sum"]
    difficulty = {item["difficulty"]: item for item in body["difficulty_stats"]}
    assert difficulty["easy"]["solved_count"] == 1
    assert difficulty["hard"]["attempted_count"] == 1
    tags = {item["tag"]["slug"]: item for item in body["tag_stats"]}
    assert tags["array"]["solved_count"] == 1
    assert tags["dynamic-programming"]["solved_count"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_training_endpoints_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/favorites")).status_code == 401
    assert (await client.get("/api/v1/users/me/training")).status_code == 401
    assert (await client.post("/api/v1/problems/1/favorite")).status_code == 401
