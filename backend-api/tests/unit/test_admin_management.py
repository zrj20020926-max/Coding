from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from io import BytesIO
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bootstrap.admin import _read_secret_file
from app.bootstrap.admin import main as admin_cli_main
from app.models.ai import AuditLog
from app.models.problem import (
    Problem,
    ProblemDifficulty,
    ProblemTag,
    ProblemVisibility,
    Tag,
)
from app.models.problem import (
    TestCase as ProblemTestCase,
)
from app.models.user import User
from app.services.admin_accounts import (
    AdminAccountError,
    AdminCreateInput,
    create_admin,
    promote_admin,
    validate_admin_password,
)
from app.services.test_data_uploads import parse_test_data_archive
from tests.unit.conftest import FakeSourceObjectStore


def strong_password() -> str:
    return f"Aa7!{uuid4().hex}"


async def register(client: AsyncClient, username: str) -> tuple[dict[str, str], dict]:
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
    return (
        {"Authorization": f"Bearer {response.json()['access_token']}"},
        response.json(),
    )


def make_archive(
    *,
    sequence: int = 1,
    input_path: str = "cases/01.in",
    output_path: str = "cases/01.out",
    input_data: bytes = b"1 2\n",
    output_data: bytes = b"3\n",
    checksum: str | None = None,
    extra_path: str | None = None,
) -> bytes:
    actual = hashlib.sha256(input_data + b"\0" + output_data).hexdigest()
    manifest = {
        "cases": [
            {
                "sequence": sequence,
                "score": 100,
                "input": input_path,
                "output": output_path,
                "checksum": checksum or actual,
            }
        ]
    }
    target = BytesIO()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(input_path, input_data)
        archive.writestr(output_path, output_data)
        if extra_path:
            archive.writestr(extra_path, b"forbidden")
    return target.getvalue()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_create_promote_idempotency_password_hash_and_audit(
    db_session: AsyncSession,
) -> None:
    password = strong_password()
    payload = AdminCreateInput(
        username="root_operator",
        email="root-operator@example.com",
        nickname="管理员",
        password=password,
    )
    first = await create_admin(db_session, payload, production=True)
    second = await create_admin(db_session, payload, production=True)
    assert first.changed is True
    assert second.changed is False
    user = await db_session.get(User, first.user_id)
    assert user is not None and user.is_admin is True
    assert user.password_hash != password
    assert user.password_hash.startswith("$argon2id$")

    normal = User(
        username="promote_me",
        email="promote@example.com",
        password_hash="existing-hash",
        nickname="普通用户",
    )
    db_session.add(normal)
    await db_session.commit()
    promoted = await promote_admin(db_session, normal.username)
    repeated = await promote_admin(db_session, normal.username)
    assert promoted.changed is True
    assert repeated.changed is False
    await db_session.refresh(normal)
    assert normal.is_admin is True and normal.auth_version == 2
    actions = (
        await db_session.scalars(select(AuditLog.action).order_by(AuditLog.created_at))
    ).all()
    assert actions == ["admin.create", "admin.promote"]


@pytest.mark.unit
def test_admin_weak_and_example_passwords_are_rejected() -> None:
    for password in (
        "password",
        "".join(("Admin", "123!", "Admin", "123!")),
        "".join(("Code", "Arena", "-R7!mN4#")),
    ):
        with pytest.raises(AdminAccountError):
            validate_admin_password(password, production=True)


@pytest.mark.unit
def test_admin_cli_reads_secret_file_and_never_echoes_password(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    password = "".join(("weak", "-secret", "-value"))
    secret = tmp_path / "admin.json"
    secret.write_text(
        "\ufeff"
        + json.dumps(
            {
                "username": "secret_admin",
                "email": "secret-admin@example.com",
                "nickname": "secret admin",
                "password": password,
            }
        ),
        encoding="utf-8",
    )
    assert _read_secret_file(secret)["username"] == "secret_admin"
    exit_code = admin_cli_main(["create", "--secret-file", str(secret)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert password not in captured.out and password not in captured.err


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_public_is_admin_read_only_and_admin_problem_filters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    normal_headers, normal_session = await register(client, "admin_filter_normal")
    assert normal_session["user"]["is_admin"] is False
    update = await client.patch(
        "/api/v1/users/me",
        json={"nickname": "still normal", "is_admin": True},
        headers=normal_headers,
    )
    assert update.status_code == 422
    assert (await client.get("/api/v1/admin/problems")).status_code == 401
    assert (
        await client.get("/api/v1/admin/problems", headers=normal_headers)
    ).status_code == 403

    admin_headers, _ = await register(client, "admin_filter_admin")
    admin = await db_session.scalar(
        select(User).where(User.username == "admin_filter_admin")
    )
    assert admin is not None
    admin.is_admin = True
    tag = Tag(slug="admin-array", name="管理数组")
    easy = Problem(
        slug="admin-easy-array",
        title="管理数组题",
        description="d",
        difficulty=ProblemDifficulty.EASY,
        input_description="i",
        output_description="o",
        visibility=ProblemVisibility.DRAFT,
    )
    hard = Problem(
        slug="admin-hard-graph",
        title="管理图题",
        description="d",
        difficulty=ProblemDifficulty.HARD,
        input_description="i",
        output_description="o",
        visibility=ProblemVisibility.PRIVATE,
    )
    easy.tag_links.append(ProblemTag(tag=tag))
    db_session.add_all([easy, hard])
    await db_session.commit()

    response = await client.get(
        "/api/v1/admin/problems?q=array&difficulty=easy&status=draft"
        "&tag=admin-array&page=1&page_size=1&sort=created_asc",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["slug"] == easy.slug
    detail = await client.get(f"/api/v1/admin/problems/{hard.id}", headers=admin_headers)
    assert detail.status_code == 200 and detail.json()["visibility"] == "private"
    readiness = await client.get(
        f"/api/v1/admin/problems/{easy.id}/readiness", headers=admin_headers
    )
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is False
    assert readiness.json()["issues"][0]["code"] == "NO_ACTIVE_TEST_SET"

    draft = await client.post(
        f"/api/v1/admin/problems/{easy.id}/test-sets",
        json={"checker_type": "exact"},
        headers=admin_headers,
    )
    deactivated = await client.post(
        f"/api/v1/admin/problems/test-sets/{draft.json()['id']}/deactivate",
        headers=admin_headers,
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "inactive"
    audit = await client.get(
        "/api/v1/admin/audit-logs?page=1&page_size=10", headers=admin_headers
    )
    assert audit.status_code == 200


@pytest.mark.unit
@pytest.mark.asyncio
async def test_admin_account_conflicts_are_explicit(db_session: AsyncSession) -> None:
    db_session.add(
        User(
            username="conflict_user",
            email="conflict@example.com",
            password_hash="hash",
            nickname="conflict",
        )
    )
    await db_session.commit()
    payload = AdminCreateInput(
        username="conflict_user",
        email="another@example.com",
        nickname="admin",
        password=strong_password(),
    )
    with pytest.raises(AdminAccountError, match="占用"):
        await create_admin(db_session, payload, production=False)


@pytest.mark.unit
def test_test_data_archive_rejects_traversal_invalid_utf8_and_checksum() -> None:
    with pytest.raises(ValueError):
        parse_test_data_archive(make_archive(extra_path="../escape.txt"))
    with pytest.raises(ValueError):
        parse_test_data_archive(make_archive(input_data=b"\xff\xfe"))
    with pytest.raises(ValueError):
        parse_test_data_archive(make_archive(checksum="0" * 64))


@pytest.mark.unit
def test_test_data_archive_rejects_symlink_duplicate_sequences_and_zip_bomb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    symlink_zip = BytesIO()
    with zipfile.ZipFile(symlink_zip, "w") as archive:
        archive.writestr("manifest.json", '{"cases":[]}')
        link = zipfile.ZipInfo("cases/link.in")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "target")
    with pytest.raises(ValueError, match="symbolic"):
        parse_test_data_archive(symlink_zip.getvalue())

    duplicate = BytesIO()
    manifest = {
        "cases": [
            {"sequence": 1, "score": 50, "input": "1.in", "output": "1.out"},
            {"sequence": 1, "score": 50, "input": "2.in", "output": "2.out"},
        ]
    }
    with zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name in ("1.in", "1.out", "2.in", "2.out"):
            archive.writestr(name, "1\n")
    with pytest.raises(ValueError, match="manifest"):
        parse_test_data_archive(duplicate.getvalue())

    from app.services import test_data_uploads

    monkeypatch.setattr(test_data_uploads.settings, "test_data_archive_max_ratio", 2)
    bomb = BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", '{"cases":[]}')
        archive.writestr("large.txt", "0" * 10_000)
    with pytest.raises(ValueError, match="compression"):
        parse_test_data_archive(bomb.getvalue())


@pytest.mark.unit
def test_test_data_archive_rejects_oversized_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import test_data_uploads

    content = make_archive()
    monkeypatch.setattr(test_data_uploads.settings, "test_data_archive_max_bytes", len(content) - 1)
    with pytest.raises(ValueError, match="too large"):
        parse_test_data_archive(content)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_test_set_batch_upload_is_atomic_and_hides_internal_fields(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_object_store: FakeSourceObjectStore,
) -> None:
    admin_headers, _ = await register(client, "archive_admin")
    admin = await db_session.scalar(select(User).where(User.username == "archive_admin"))
    assert admin is not None
    admin.is_admin = True
    problem = Problem(
        slug="archive-problem",
        title="批量上传题",
        description="d",
        difficulty=ProblemDifficulty.EASY,
        input_description="i",
        output_description="o",
        visibility=ProblemVisibility.DRAFT,
    )
    db_session.add(problem)
    await db_session.commit()
    created = await client.post(
        f"/api/v1/admin/problems/{problem.id}/test-sets",
        json={"checker_type": "exact"},
        headers=admin_headers,
    )
    test_set_id = created.json()["id"]

    unsafe = await client.post(
        f"/api/v1/admin/problems/test-sets/{test_set_id}/cases/upload",
        files={"archive": ("cases.zip", make_archive(extra_path="../escape"), "application/zip")},
        headers=admin_headers,
    )
    assert unsafe.status_code == 422
    assert fake_object_store.test_objects == {}

    uploaded = await client.post(
        f"/api/v1/admin/problems/test-sets/{test_set_id}/cases/upload",
        files={"archive": ("cases.zip", make_archive(), "application/zip")},
        headers=admin_headers,
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["uploaded_count"] == 1
    serialized = uploaded.text
    for hidden in ("object_key", "checksum", "hidden_input", "hidden_output"):
        assert hidden not in serialized
    assert await db_session.scalar(select(func.count(ProblemTestCase.id))) == 1
    assert len(fake_object_store.test_objects) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_test_set_upload_failure_has_no_partial_database_rows(
    client: AsyncClient,
    db_session: AsyncSession,
    fake_object_store: FakeSourceObjectStore,
) -> None:
    admin_headers, _ = await register(client, "archive_failure_admin")
    admin = await db_session.scalar(
        select(User).where(User.username == "archive_failure_admin")
    )
    assert admin is not None
    admin.is_admin = True
    problem = Problem(
        slug="archive-failure-problem",
        title="上传失败题",
        description="d",
        difficulty=ProblemDifficulty.EASY,
        input_description="i",
        output_description="o",
        visibility=ProblemVisibility.DRAFT,
    )
    db_session.add(problem)
    await db_session.commit()
    created = await client.post(
        f"/api/v1/admin/problems/{problem.id}/test-sets",
        json={"checker_type": "exact"},
        headers=admin_headers,
    )
    fake_object_store.fail_test_put_after = 1
    failed = await client.post(
        f"/api/v1/admin/problems/test-sets/{created.json()['id']}/cases/upload",
        files={"archive": ("cases.zip", make_archive(), "application/zip")},
        headers=admin_headers,
    )
    assert failed.status_code == 503
    assert await db_session.scalar(select(func.count(ProblemTestCase.id))) == 0
    assert fake_object_store.test_objects == {}
