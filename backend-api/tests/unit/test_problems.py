import hashlib
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
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
from app.models.user import User
from app.services.problem_import import import_problem_seed, load_seed_document
from tests.unit.conftest import FakeSourceObjectStore


async def register_user(client: AsyncClient, username: str = "catalog_user") -> dict[str, str]:
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


async def seed_catalog(db: AsyncSession) -> dict[str, Problem]:
    array = Tag(slug="array", name="数组")
    graph = Tag(slug="graph", name="图论")
    problems = {
        "sum": Problem(
            slug="a-plus-b",
            title="A+B 问题",
            description="求和",
            difficulty=ProblemDifficulty.EASY,
            input_description="两个整数",
            output_description="整数和",
            sample_input="1 2\n",
            sample_output="3\n",
            visibility=ProblemVisibility.PUBLIC,
            accepted_count=80,
            submission_count=100,
            tag_links=[ProblemTag(tag=array)],
        ),
        "shortest": Problem(
            slug="shortest-path",
            title="最短路径",
            description="图上最短路",
            difficulty=ProblemDifficulty.HARD,
            input_description="图",
            output_description="距离",
            visibility=ProblemVisibility.PUBLIC,
            accepted_count=10,
            submission_count=100,
            tag_links=[ProblemTag(tag=graph)],
        ),
        "window": Problem(
            slug="window-sum",
            title="窗口总和",
            description="窗口",
            difficulty=ProblemDifficulty.MEDIUM,
            input_description="数组",
            output_description="和",
            visibility=ProblemVisibility.PUBLIC,
            accepted_count=0,
            submission_count=0,
            tag_links=[ProblemTag(tag=array)],
        ),
        "draft": Problem(
            slug="secret-draft",
            title="内部草稿",
            description="不可见",
            difficulty=ProblemDifficulty.EASY,
            input_description="隐藏",
            output_description="隐藏",
            visibility=ProblemVisibility.DRAFT,
        ),
        "private": Problem(
            slug="offline-problem",
            title="已下线题",
            description="不可见",
            difficulty=ProblemDifficulty.EASY,
            input_description="隐藏",
            output_description="隐藏",
            visibility=ProblemVisibility.PRIVATE,
        ),
    }
    db.add_all(
        [
            *problems.values(),
            Language(
                slug="python",
                display_name="Python",
                version="3.12",
                monaco_language="python",
                source_filename="main.py",
                compile_command=None,
                run_command="python -I main.py",
                docker_image="private.registry/judge-python:3.12",
                enabled=True,
                sort_order=10,
            ),
            Language(
                slug="disabled",
                display_name="Disabled",
                version="1",
                monaco_language="text",
                source_filename="main.txt",
                compile_command="secret compiler",
                run_command="secret runner",
                docker_image="secret image",
                enabled=False,
                sort_order=20,
            ),
        ]
    )
    await db.commit()
    return problems


@pytest.mark.unit
@pytest.mark.asyncio
async def test_public_problem_pagination_filters_and_sort(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_catalog(db_session)

    response = await client.get("/api/v1/problems?page=1&page_size=2&sort=title")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert [item["slug"] for item in body["items"]] == ["a-plus-b", "shortest-path"]
    assert "solved" not in body["items"][0]

    filtered = await client.get(
        "/api/v1/problems",
        params={"q": "路径", "difficulty": "hard", "tag": "graph"},
    )
    assert filtered.status_code == 200
    assert [item["slug"] for item in filtered.json()["items"]] == ["shortest-path"]

    acceptance = await client.get("/api/v1/problems?sort=acceptance")
    assert [item["slug"] for item in acceptance.json()["items"]] == [
        "a-plus-b",
        "shortest-path",
        "window-sum",
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_visibility_progress_and_status_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problems = await seed_catalog(db_session)
    assert (await client.get(f"/api/v1/problems/{problems['draft'].id}")).status_code == 404
    assert (await client.get(f"/api/v1/problems/{problems['private'].id}")).status_code == 404
    assert (await client.get("/api/v1/problems?status=solved")).status_code == 401

    headers = await register_user(client)
    user = await db_session.scalar(select(User).where(User.username == "catalog_user"))
    assert user is not None
    db_session.add_all(
        [
            UserProblemProgress(
                user_id=user.id,
                problem_id=problems["sum"].id,
                attempt_count=2,
                accepted=True,
            ),
            UserProblemProgress(
                user_id=user.id,
                problem_id=problems["shortest"].id,
                attempt_count=3,
                accepted=False,
            ),
            Favorite(user_id=user.id, problem_id=problems["window"].id),
        ]
    )
    await db_session.commit()

    all_items = (await client.get("/api/v1/problems", headers=headers)).json()["items"]
    by_slug = {item["slug"]: item for item in all_items}
    assert by_slug["a-plus-b"]["solved"] is True
    assert by_slug["a-plus-b"]["favorited"] is False
    assert by_slug["shortest-path"]["attempted"] is True
    assert by_slug["window-sum"]["attempt_count"] == 0
    assert by_slug["window-sum"]["favorited"] is True

    solved = await client.get("/api/v1/problems?status=solved", headers=headers)
    attempted = await client.get("/api/v1/problems?status=attempted", headers=headers)
    unattempted = await client.get("/api/v1/problems?status=unattempted", headers=headers)
    favorited = await client.get("/api/v1/problems?status=favorited", headers=headers)
    assert [item["slug"] for item in solved.json()["items"]] == ["a-plus-b"]
    assert [item["slug"] for item in attempted.json()["items"]] == ["shortest-path"]
    assert [item["slug"] for item in unattempted.json()["items"]] == ["window-sum"]
    assert [item["slug"] for item in favorited.json()["items"]] == ["window-sum"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_public_responses_do_not_leak_runtime_configuration(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problems = await seed_catalog(db_session)
    languages = await client.get("/api/v1/languages")
    assert languages.status_code == 200
    assert [item["slug"] for item in languages.json()] == ["python"]

    detail = await client.get(f"/api/v1/problems/{problems['sum'].id}")
    tags = await client.get("/api/v1/tags")
    serialized = json.dumps(
        {"languages": languages.json(), "problem": detail.json(), "tags": tags.json()}
    )
    for forbidden in (
        "compile_command",
        "run_command",
        "docker_image",
        "object_key",
        "test_cases",
        "private.registry",
    ):
        assert forbidden not in serialized

    openapi = json.dumps(app.openapi())
    for forbidden_schema_field in ("compile_command", "run_command", "docker_image"):
        assert forbidden_schema_field not in openapi


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_permissions_crud_publish_and_offline(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_object_store: FakeSourceObjectStore,
) -> None:
    await seed_catalog(db_session)
    payload = {
        "slug": "two-sum-acm",
        "title": "两数之和 ACM",
        "description": "描述",
        "difficulty": "easy",
        "input_description": "输入",
        "output_description": "输出",
        "tag_slugs": ["array"],
    }
    assert (await client.post("/api/v1/admin/problems", json=payload)).status_code == 401

    headers = await register_user(client, "normal_user")
    forbidden = await client.post("/api/v1/admin/problems", json=payload, headers=headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "FORBIDDEN"

    user = await db_session.scalar(select(User).where(User.username == "normal_user"))
    assert user is not None
    user.is_admin = True
    await db_session.commit()

    created = await client.post("/api/v1/admin/problems", json=payload, headers=headers)
    assert created.status_code == 201
    problem_id = created.json()["id"]
    assert created.json()["visibility"] == "draft"
    assert (await client.get(f"/api/v1/problems/{problem_id}")).status_code == 404

    updated = await client.patch(
        f"/api/v1/admin/problems/{problem_id}",
        json={"title": "两数求和", "tag_slugs": ["graph"]},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["tags"][0]["slug"] == "graph"

    published = await client.post(
        f"/api/v1/admin/problems/{problem_id}/publish", headers=headers
    )
    assert published.status_code == 409
    assert published.json()["detail"] == {
        "code": "PROBLEM_NOT_READY",
        "message": "题目缺少有效的隐藏测试集",
        "issues": [],
    }

    db_session.add(
        Language(
            slug="cpp",
            display_name="C++",
            version="C++20",
            monaco_language="cpp",
            source_filename="main.cpp",
            compile_command="internal",
            run_command="internal",
            docker_image="internal",
            enabled=True,
        )
    )
    await db_session.commit()
    test_set_response = await client.post(
        f"/api/v1/admin/problems/{problem_id}/test-sets",
        json={"checker_type": "exact"},
        headers=headers,
    )
    assert test_set_response.status_code == 201
    test_set_id = test_set_response.json()["id"]
    stdin = b"1 2\n"
    expected = b"3\n"
    fake_object_store.test_objects["tests/input"] = stdin
    fake_object_store.test_objects["tests/output"] = expected
    checksum = hashlib.sha256(stdin + b"\0" + expected).hexdigest()
    added = await client.post(
        f"/api/v1/admin/problems/test-sets/{test_set_id}/cases",
        json={
            "sequence": 1,
            "score": "100.00",
            "input_object_key": "tests/input",
            "output_object_key": "tests/output",
            "checksum": checksum,
        },
        headers=headers,
    )
    assert added.status_code == 201
    assert "object_key" not in added.text and "checksum" not in added.text
    validated = await client.post(
        f"/api/v1/admin/problems/test-sets/{test_set_id}/validate", headers=headers
    )
    assert validated.status_code == 200
    assert validated.json()["issues"] == []
    activated = await client.post(
        f"/api/v1/admin/problems/test-sets/{test_set_id}/activate", headers=headers
    )
    assert activated.status_code == 200
    del fake_object_store.test_objects["tests/input"]
    missing_on_publish = await client.post(
        f"/api/v1/admin/problems/{problem_id}/publish", headers=headers
    )
    assert missing_on_publish.status_code == 409
    assert missing_on_publish.json()["detail"]["issues"][0]["code"] == (
        "TEST_DATA_UNAVAILABLE"
    )
    assert "tests/input" not in missing_on_publish.text

    fake_object_store.test_objects["tests/input"] = stdin
    fake_object_store.test_objects["tests/output"] = b"tampered\n"
    checksum_on_publish = await client.post(
        f"/api/v1/admin/problems/{problem_id}/publish", headers=headers
    )
    assert checksum_on_publish.status_code == 409
    issue_codes = {
        issue["code"] for issue in checksum_on_publish.json()["detail"]["issues"]
    }
    assert "CHECKSUM_MISMATCH" in issue_codes
    assert checksum not in checksum_on_publish.text

    fake_object_store.test_objects["tests/output"] = expected
    published = await client.post(
        f"/api/v1/admin/problems/{problem_id}/publish", headers=headers
    )
    assert published.status_code == 200
    assert (await client.get(f"/api/v1/problems/{problem_id}")).status_code == 200

    offline = await client.post(
        f"/api/v1/admin/problems/{problem_id}/offline", headers=headers
    )
    assert offline.status_code == 200
    assert offline.json()["visibility"] == "private"
    assert (await client.get(f"/api/v1/problems/{problem_id}")).status_code == 404


@pytest.mark.unit
@pytest.mark.asyncio
async def test_yaml_and_json_seed_import_is_idempotent(
    db_session: AsyncSession, tmp_path
) -> None:
    seed_data = {
        "tags": [{"slug": "array", "name": "数组"}],
        "problems": [
            {
                "slug": "seeded-problem",
                "title": "种子题",
                "description": "描述",
                "difficulty": "easy",
                "input_description": "输入",
                "output_description": "输出",
                "visibility": "draft",
                "tag_slugs": ["array"],
            }
        ],
    }
    json_path = tmp_path / "problems.json"
    json_path.write_text(json.dumps(seed_data, ensure_ascii=False), encoding="utf-8")
    document = load_seed_document(json_path)
    first = await import_problem_seed(db_session, document)
    second = await import_problem_seed(db_session, document)
    assert first.problems_created == 1
    assert second.problems_created == 0

    yaml_path = tmp_path / "problems.yaml"
    yaml_path.write_text(
        "tags:\n  - slug: array\n    name: 数组\nproblems:\n"
        "  - slug: seeded-problem\n    title: YAML 更新题\n    description: 描述\n"
        "    difficulty: medium\n    input_description: 输入\n    output_description: 输出\n"
        "    visibility: draft\n    tag_slugs: [array]\n",
        encoding="utf-8",
    )
    await import_problem_seed(db_session, load_seed_document(yaml_path))

    problems = (await db_session.scalars(select(Problem))).all()
    links = (await db_session.scalars(select(ProblemTag))).all()
    assert len(problems) == 1
    assert len(links) == 1
    assert problems[0].title == "YAML 更新题"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_test_set_admin_endpoints_reject_non_admin_and_never_leak_hidden_fields(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_object_store: FakeSourceObjectStore,
) -> None:
    problems = await seed_catalog(db_session)
    normal_headers = await register_user(client, "test_set_normal")
    forbidden = await client.post(
        f"/api/v1/admin/problems/{problems['draft'].id}/test-sets",
        json={"checker_type": "exact"},
        headers=normal_headers,
    )
    assert forbidden.status_code == 403

    user = await db_session.scalar(select(User).where(User.username == "test_set_normal"))
    assert user is not None
    user.is_admin = True
    db_session.add(
        Language(
            slug="cpp",
            display_name="C++",
            version="C++20",
            monaco_language="cpp",
            source_filename="main.cpp",
            compile_command="private compile command",
            run_command="private run command",
            docker_image="private image",
            enabled=True,
        )
    )
    await db_session.commit()
    created = await client.post(
        f"/api/v1/admin/problems/{problems['draft'].id}/test-sets",
        json={"checker_type": "exact"},
        headers=normal_headers,
    )
    test_set_id = created.json()["id"]
    missing = await client.post(
        f"/api/v1/admin/problems/test-sets/{test_set_id}/cases",
        json={
            "sequence": 1,
            "score": 100,
            "input_object_key": "secret/missing-input",
            "output_object_key": "secret/missing-output",
            "checksum": "a" * 64,
        },
        headers=normal_headers,
    )
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "TEST_DATA_UNAVAILABLE"
    assert "secret/" not in missing.text and "a" * 64 not in missing.text

    fake_object_store.test_objects["secret/input"] = b"1 2\n"
    fake_object_store.test_objects["secret/output"] = b"3\n"
    mismatch = await client.post(
        f"/api/v1/admin/problems/test-sets/{test_set_id}/cases",
        json={
            "sequence": 1,
            "score": 100,
            "input_object_key": "secret/input",
            "output_object_key": "secret/output",
            "checksum": "b" * 64,
        },
        headers=normal_headers,
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["detail"]["code"] == "TEST_DATA_CHECKSUM_MISMATCH"
    assert "secret/" not in mismatch.text and "b" * 64 not in mismatch.text

    listed = await client.get(
        f"/api/v1/admin/problems/{problems['draft'].id}/test-sets",
        headers=normal_headers,
    )
    serialized = listed.text
    for forbidden_field in (
        "input_object_key",
        "output_object_key",
        "checksum",
        "docker_image",
        "compile_command",
    ):
        assert forbidden_field not in serialized
