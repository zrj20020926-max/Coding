from datetime import datetime, timedelta, timezone

import fakeredis.aioredis
import jwt
import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import auth as auth_routes
from app.core.config import DEFAULT_JWT_SECRET, Settings, settings
from app.core.security import DUMMY_PASSWORD_HASH
from app.models.user import User
from app.services.auth_sessions import parse_refresh_token, refresh_session_key

pytestmark = pytest.mark.unit


async def register_account(client: AsyncClient, suffix: str = "secure"):
    return await client.post(
        "/api/v1/auth/register",
        json={
            "username": f"candidate_{suffix}",
            "email": f"candidate-{suffix}@example.com",
            "password": "safe-password-123",
            "nickname": "安全测试用户",
        },
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_access_expiry_and_http_only_refresh_cookie(client: AsyncClient) -> None:
    registered = await register_account(client)
    assert registered.status_code == 201
    assert registered.json()["expires_in"] == 900
    set_cookie = registered.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert settings.refresh_cookie_name not in registered.json()

    claims = jwt.decode(registered.json()["access_token"], options={"verify_signature": False})
    claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired_token = jwt.encode(
        claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    expired_response = await client.get("/api/v1/users/me", headers=bearer(expired_token))
    assert expired_response.status_code == 401

    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"] != registered.json()["access_token"]


@pytest.mark.asyncio
async def test_expired_refresh_session_is_rejected(
    client: AsyncClient,
    fake_redis: fakeredis.aioredis.FakeRedis,
) -> None:
    registered = await register_account(client)
    raw_token = registered.cookies.get(settings.refresh_cookie_name)
    assert raw_token is not None
    session_id, _ = parse_refresh_token(raw_token)
    await fake_redis.delete(refresh_session_key(session_id))

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"
    assert "Max-Age=0" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_refresh_rotation_detects_replay(client: AsyncClient) -> None:
    registered = await register_account(client)
    old_refresh = registered.cookies.get(settings.refresh_cookie_name)
    assert old_refresh is not None

    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    new_refresh = refreshed.cookies.get(settings.refresh_cookie_name)
    assert new_refresh is not None and new_refresh != old_refresh

    client.cookies.clear()
    client.cookies.set(settings.refresh_cookie_name, old_refresh, path=settings.refresh_cookie_path)
    replay = await client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401
    assert replay.json()["detail"]["code"] == "REFRESH_TOKEN_REUSED"

    client.cookies.clear()
    client.cookies.set(settings.refresh_cookie_name, new_refresh, path=settings.refresh_cookie_path)
    revoked_family = await client.post("/api/v1/auth/refresh")
    assert revoked_family.status_code == 401
    assert revoked_family.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_disabled_account_cannot_use_access_or_refresh(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    registered = await register_account(client)
    token = registered.json()["access_token"]
    user = await db_session.scalar(select(User).where(User.username == "candidate_secure"))
    assert user is not None
    user.is_active = False
    await db_session.commit()

    profile = await client.get("/api/v1/users/me", headers=bearer(token))
    assert profile.status_code == 401

    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 403
    assert refreshed.json()["detail"]["code"] == "ACCOUNT_DISABLED"


@pytest.mark.asyncio
async def test_logout_all_revokes_every_session(client: AsyncClient) -> None:
    registered = await register_account(client)
    first_token = registered.json()["access_token"]
    second_login = await client.post(
        "/api/v1/auth/login",
        json={"account": "candidate_secure", "password": "safe-password-123"},
    )
    second_token = second_login.json()["access_token"]
    second_refresh = second_login.cookies.get(settings.refresh_cookie_name)
    assert second_refresh is not None

    logged_out = await client.post("/api/v1/auth/logout-all", headers=bearer(second_token))
    assert logged_out.status_code == 204
    assert (await client.get("/api/v1/users/me", headers=bearer(first_token))).status_code == 401
    assert (await client.get("/api/v1/users/me", headers=bearer(second_token))).status_code == 401

    client.cookies.set(
        settings.refresh_cookie_name, second_refresh, path=settings.refresh_cookie_path
    )
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


@pytest.mark.asyncio
async def test_change_password_revokes_sessions_and_old_password(client: AsyncClient) -> None:
    registered = await register_account(client)
    old_token = registered.json()["access_token"]
    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=bearer(old_token),
        json={
            "current_password": "safe-password-123",
            "new_password": "new-safe-password-456",
        },
    )
    assert changed.status_code == 204
    assert (await client.get("/api/v1/users/me", headers=bearer(old_token))).status_code == 401

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"account": "candidate_secure", "password": "safe-password-123"},
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"account": "candidate_secure", "password": "new-safe-password-456"},
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_missing_account_uses_dummy_password_hash(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed_hashes: list[str] = []

    def verify_with_spy(_: str, hashed_password: str) -> bool:
        observed_hashes.append(hashed_password)
        return False

    monkeypatch.setattr(auth_routes, "verify_password", verify_with_spy)
    response = await client.post(
        "/api/v1/auth/login",
        json={"account": "missing@example.com", "password": "safe-password-123"},
    )
    assert response.status_code == 401
    assert observed_hashes == [DUMMY_PASSWORD_HASH]


@pytest.mark.asyncio
async def test_login_rate_limits_account_and_ip_dimensions(
    client: AsyncClient,
    fake_redis: fakeredis.aioredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_routes, "verify_password", lambda *_: False)
    monkeypatch.setattr(settings, "login_rate_limit_ip_attempts", 100)
    monkeypatch.setattr(settings, "login_rate_limit_account_attempts", 2)

    payload = {"account": "target@example.com", "password": "safe-password-123"}
    assert (await client.post("/api/v1/auth/login", json=payload)).status_code == 401
    assert (await client.post("/api/v1/auth/login", json=payload)).status_code == 401
    limited = await client.post("/api/v1/auth/login", json=payload)
    assert limited.status_code == 429
    assert limited.json()["detail"] == {
        "code": "RATE_LIMITED",
        "message": "请求过于频繁，请稍后再试",
    }
    assert int(limited.headers["retry-after"]) > 0

    await fake_redis.flushall()
    monkeypatch.setattr(settings, "login_rate_limit_ip_attempts", 2)
    monkeypatch.setattr(settings, "login_rate_limit_account_attempts", 100)
    for account in ("one@example.com", "two@example.com"):
        assert (
            await client.post(
                "/api/v1/auth/login",
                json={"account": account, "password": "safe-password-123"},
            )
        ).status_code == 401
    ip_limited = await client.post(
        "/api/v1/auth/login",
        json={"account": "three@example.com", "password": "safe-password-123"},
    )
    assert ip_limited.status_code == 429


@pytest.mark.asyncio
async def test_registration_is_rate_limited(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "register_rate_limit_ip_attempts", 2)
    monkeypatch.setattr(settings, "register_rate_limit_account_attempts", 100)
    assert (await register_account(client, "one")).status_code == 201
    assert (await register_account(client, "two")).status_code == 201
    limited = await register_account(client, "three")
    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == "RATE_LIMITED"


def test_production_rejects_default_secret_and_insecure_cookies() -> None:
    with pytest.raises(ValidationError, match="non-default JWT secret"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key=DEFAULT_JWT_SECRET,
            refresh_cookie_secure=True,
        )

    with pytest.raises(ValidationError, match="refresh cookies must be Secure"):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret_key="a-production-secret-that-is-longer-than-32-characters",
            refresh_cookie_secure=False,
        )
