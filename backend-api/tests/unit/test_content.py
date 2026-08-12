from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AuditLog
from app.models.content import (
    Collection,
    ContentModerationAction,
    ContentReport,
    Discussion,
)
from app.models.problem import (
    Problem,
    ProblemDifficulty,
    ProblemVisibility,
    UserProblemProgress,
)
from app.models.user import User
from app.services import collections as collections_service
from app.services.collections import current_content_date


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


async def make_admin(
    client: AsyncClient, db: AsyncSession, username: str
) -> dict[str, str]:
    headers = await register(client, username)
    user = await db.scalar(select(User).where(User.username == username))
    assert user is not None
    user.is_admin = True
    await db.commit()
    return headers


async def seed_content_problems(db: AsyncSession) -> tuple[Problem, Problem, Problem]:
    first = Problem(
        slug="content-first",
        title="内容题一",
        description="description",
        difficulty=ProblemDifficulty.EASY,
        input_description="input",
        output_description="output",
        visibility=ProblemVisibility.PUBLIC,
    )
    second = Problem(
        slug="content-second",
        title="内容题二",
        description="description",
        difficulty=ProblemDifficulty.MEDIUM,
        input_description="input",
        output_description="output",
        visibility=ProblemVisibility.PUBLIC,
    )
    offline = Problem(
        slug="content-offline",
        title="下线题",
        description="description",
        difficulty=ProblemDifficulty.HARD,
        input_description="input",
        output_description="output",
        visibility=ProblemVisibility.PRIVATE,
    )
    db.add_all([first, second, offline])
    await db.commit()
    return first, second, offline


@pytest.mark.unit
@pytest.mark.asyncio
async def test_collection_admin_order_publish_and_personal_progress(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first, second, offline = await seed_content_problems(db_session)
    admin_headers = await make_admin(client, db_session, "collection_admin")
    user_headers = await register(client, "collection_user")

    forbidden = await client.post(
        "/api/v1/admin/collections",
        json={"slug": "forbidden", "title": "forbidden"},
        headers=user_headers,
    )
    assert forbidden.status_code == 403

    created = await client.post(
        "/api/v1/admin/collections",
        json={
            "slug": "interview-top",
            "title": "面试 TOP",
            "company": "字节",
            "problem_ids": [second.id, offline.id, first.id],
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    collection_id = created.json()["id"]
    assert created.json()["is_public"] is False
    assert (await client.get("/api/v1/collections")).json()["total"] == 0
    assert (
        await client.get("/api/v1/admin/collections", headers=user_headers)
    ).status_code == 403
    admin_listing = await client.get(
        "/api/v1/admin/collections?page=1&page_size=1",
        headers=admin_headers,
    )
    assert admin_listing.status_code == 200
    assert admin_listing.json()["total"] == 1
    assert admin_listing.json()["items"][0]["is_public"] is False
    admin_detail = await client.get(
        f"/api/v1/admin/collections/{collection_id}",
        headers=admin_headers,
    )
    assert admin_detail.status_code == 200
    assert len(admin_detail.json()["problems"]) == 3

    reordered = await client.put(
        f"/api/v1/admin/collections/{collection_id}/problems",
        json={"problem_ids": [first.id, second.id, offline.id]},
        headers=admin_headers,
    )
    assert [item["problem"]["id"] for item in reordered.json()["problems"]] == [
        first.id,
        second.id,
        offline.id,
    ]
    failed_reorder = await client.put(
        f"/api/v1/admin/collections/{collection_id}/problems",
        json={"problem_ids": [first.id, 999999999]},
        headers=admin_headers,
    )
    assert failed_reorder.status_code == 400
    unchanged = await client.get(
        f"/api/v1/admin/collections/{collection_id}", headers=admin_headers
    )
    assert [item["problem"]["id"] for item in unchanged.json()["problems"]] == [
        first.id,
        second.id,
        offline.id,
    ]
    published = await client.post(
        f"/api/v1/admin/collections/{collection_id}/publish",
        headers=admin_headers,
    )
    assert published.status_code == 200

    user = await db_session.scalar(select(User).where(User.username == "collection_user"))
    assert user is not None
    db_session.add(
        UserProblemProgress(
            user_id=user.id,
            problem_id=second.id,
            attempt_count=2,
            accepted=True,
        )
    )
    await db_session.commit()

    listing = await client.get(
        "/api/v1/collections?page=1&page_size=1", headers=user_headers
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["problem_count"] == 2
    assert listing.json()["items"][0]["solved_count"] == 1
    assert listing.json()["items"][0]["completion_rate"] == 50.0

    detail = await client.get(
        "/api/v1/collections/interview-top?page=1&page_size=1",
        headers=user_headers,
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["problem_count"] == 2
    assert body["pages"] == 2
    assert [item["problem"]["id"] for item in body["problems"]] == [first.id]
    assert all(item["problem"]["id"] != offline.id for item in body["problems"])

    offline_response = await client.post(
        f"/api/v1/admin/collections/{collection_id}/offline",
        headers=admin_headers,
    )
    assert offline_response.status_code == 200
    assert (await client.get("/api/v1/collections/interview-top")).status_code == 404


@pytest.mark.unit
@pytest.mark.asyncio
async def test_daily_challenge_uses_server_date_and_hides_offline_problem(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first, _, offline = await seed_content_problems(db_session)
    admin_headers = await make_admin(client, db_session, "daily_admin")
    today: date = current_content_date()

    configured = await client.put(
        f"/api/v1/admin/daily-challenges/{today.isoformat()}",
        json={"problem_id": first.id},
        headers=admin_headers,
    )
    assert configured.status_code == 200
    daily = await client.get("/api/v1/daily-challenge")
    assert daily.status_code == 200
    assert daily.json()["challenge_date"] == today.isoformat()
    assert daily.json()["timezone"] == "Asia/Shanghai"
    assert daily.json()["problem"]["slug"] == "content-first"

    date_range = await client.get(
        f"/api/v1/admin/daily-challenges?start_date={today.isoformat()}"
        f"&end_date={today.isoformat()}&page=1&page_size=20",
        headers=admin_headers,
    )
    assert date_range.status_code == 200
    assert date_range.json()["total"] == 1
    assert date_range.json()["items"][0]["timezone"] == "Asia/Shanghai"

    await client.put(
        f"/api/v1/admin/daily-challenges/{today.isoformat()}",
        json={"problem_id": offline.id},
        headers=admin_headers,
    )
    assert (await client.get("/api/v1/daily-challenge")).status_code == 404
    deleted = await client.delete(
        f"/api/v1/admin/daily-challenges/{today.isoformat()}", headers=admin_headers
    )
    assert deleted.status_code == 204
    assert (
        await client.get(
            f"/api/v1/admin/daily-challenges?start_date={today.isoformat()}"
            f"&end_date={today.isoformat()}",
            headers=admin_headers,
        )
    ).json()["total"] == 0


@pytest.mark.unit
def test_content_date_crosses_day_in_configured_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedDateTime:
        @classmethod
        def now(cls, tz):  # noqa: ANN001
            return datetime(2026, 8, 9, 16, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(collections_service, "datetime", FixedDateTime)
    assert current_content_date() == date(2026, 8, 10)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_discussion_moderation_lock_reports_and_permissions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, _, _ = await seed_content_problems(db_session)
    problem_id = problem.id
    admin_headers = await make_admin(client, db_session, "discussion_admin")
    alice_headers = await register(client, "discussion_alice")
    bob_headers = await register(client, "discussion_bob")

    clean = await client.post(
        f"/api/v1/problems/{problem.id}/discussions",
        json={"title": "解题思路", "content": "使用前缀和。"},
        headers=alice_headers,
    )
    assert clean.status_code == 201
    discussion_id = clean.json()["id"]
    pending = await client.post(
        f"/api/v1/problems/{problem.id}/discussions",
        json={"title": "待审核", "content": "包含赌博敏感词"},
        headers=alice_headers,
    )
    assert pending.json()["review_status"] == "pending"

    anonymous = await client.get(f"/api/v1/problems/{problem.id}/discussions")
    owner = await client.get(
        f"/api/v1/problems/{problem.id}/discussions", headers=alice_headers
    )
    assert anonymous.json()["total"] == 1
    assert owner.json()["total"] == 2

    approved = await client.patch(
        f"/api/v1/admin/discussions/{pending.json()['id']}/moderation",
        json={"review_status": "approved", "reason": "人工复核"},
        headers=admin_headers,
    )
    assert approved.status_code == 200

    root = await client.post(
        f"/api/v1/discussions/{discussion_id}/comments",
        json={"content": "root"},
        headers=bob_headers,
    )
    parent_id = root.json()["id"]
    pending_comment = await client.post(
        f"/api/v1/discussions/{discussion_id}/comments",
        json={"content": "赌博内容"},
        headers=bob_headers,
    )
    assert pending_comment.json()["review_status"] == "pending"
    hidden_report = await client.post(
        f"/api/v1/comments/{pending_comment.json()['id']}/reports",
        json={"reason": "不应泄露待审评论"},
        headers=alice_headers,
    )
    assert hidden_report.status_code == 404
    for depth in range(1, 4):
        reply = await client.post(
            f"/api/v1/discussions/{discussion_id}/comments",
            json={"content": f"reply {depth}", "parent_id": parent_id},
            headers=alice_headers,
        )
        assert reply.status_code == 201
        assert reply.json()["depth"] == depth
        parent_id = reply.json()["id"]
    too_deep = await client.post(
        f"/api/v1/discussions/{discussion_id}/comments",
        json={"content": "too deep", "parent_id": parent_id},
        headers=bob_headers,
    )
    assert too_deep.status_code == 400
    assert too_deep.json()["detail"]["code"] == "REPLY_DEPTH_EXCEEDED"

    forbidden_edit = await client.patch(
        f"/api/v1/discussions/{discussion_id}",
        json={"title": "越权修改"},
        headers=bob_headers,
    )
    assert forbidden_edit.status_code == 403

    first_report = await client.post(
        f"/api/v1/discussions/{discussion_id}/reports",
        json={"reason": "疑似错误内容"},
        headers=bob_headers,
    )
    duplicate_report = await client.post(
        f"/api/v1/discussions/{discussion_id}/reports",
        json={"reason": "重复举报"},
        headers=bob_headers,
    )
    assert first_report.json()["created"] is True
    assert duplicate_report.json()["created"] is False
    discussion = await db_session.get(Discussion, discussion_id)
    assert discussion is not None
    await db_session.refresh(discussion)
    assert discussion.report_count == 1

    reports = await client.get(
        "/api/v1/admin/content-reports?page=1&page_size=1",
        headers=admin_headers,
    )
    assert reports.status_code == 200
    assert reports.json()["total"] == 1
    handled = await client.patch(
        f"/api/v1/admin/content-reports/{first_report.json()['report_id']}",
        json={"status": "resolved", "reason": "已处理"},
        headers=admin_headers,
    )
    assert handled.json()["status"] == "resolved"

    locked = await client.patch(
        f"/api/v1/admin/discussions/{discussion_id}/controls",
        json={"is_locked": True, "is_pinned": True},
        headers=admin_headers,
    )
    assert locked.json()["is_locked"] is True
    assert (
        await client.post(
            f"/api/v1/discussions/{discussion_id}/comments",
            json={"content": "locked"},
            headers=bob_headers,
        )
    ).status_code == 423
    action_count = await db_session.scalar(select(func.count(ContentModerationAction.id)))
    assert action_count == 3
    audit_actions = set((await db_session.scalars(select(AuditLog.action))).all())
    assert {
        "discussion.moderate",
        "discussion.controls",
        "report.handle",
    }.issubset(audit_actions)

    persisted_problem = await db_session.get(Problem, problem_id)
    assert persisted_problem is not None
    persisted_problem.visibility = ProblemVisibility.PRIVATE
    await db_session.commit()
    assert (
        await client.get(f"/api/v1/problems/{problem_id}/discussions")
    ).status_code == 404
    assert (await client.get(f"/api/v1/discussions/{discussion_id}")).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/comments/{root.json()['id']}",
            json={"content": "offline edit"},
            headers=bob_headers,
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/comments/{root.json()['id']}/reports",
            json={"reason": "offline report"},
            headers=alice_headers,
        )
    ).status_code == 404


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deleted_author_and_xss_payload_are_returned_safely_as_data(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    problem, _, _ = await seed_content_problems(db_session)
    headers = await register(client, "deleted_author")
    payload = "<img src=x onerror=alert(1)> **safe markdown**"
    created = await client.post(
        f"/api/v1/problems/{problem.id}/discussions",
        json={"title": "XSS 测试", "content": payload},
        headers=headers,
    )
    discussion = await db_session.get(Discussion, created.json()["id"])
    assert discussion is not None
    discussion.user_id = None
    await db_session.commit()

    detail = await client.get(f"/api/v1/discussions/{discussion.id}")
    assert detail.status_code == 200
    assert detail.json()["discussion"]["author"] is None
    assert detail.json()["discussion"]["content"] == payload
    assert "rendered_html" not in detail.json()["discussion"]

    assert await db_session.scalar(select(func.count(ContentReport.id))) == 0
    assert await db_session.scalar(select(func.count(Collection.id))) == 0
