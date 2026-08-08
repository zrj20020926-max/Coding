import pytest
from httpx import AsyncClient


@pytest.mark.unit
@pytest.mark.asyncio
async def test_register_login_profile_and_logout(client: AsyncClient) -> None:
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "Candidate_01",
            "email": "candidate@example.com",
            "password": "safe-password-123",
            "nickname": "候选人一号",
        },
    )
    assert register_response.status_code == 201
    register_body = register_response.json()
    assert register_body["user"]["username"] == "candidate_01"
    assert register_body["token_type"] == "bearer"

    duplicate_response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "candidate_01",
            "email": "another@example.com",
            "password": "safe-password-123",
            "nickname": "重复用户",
        },
    )
    assert duplicate_response.status_code == 409

    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"account": "candidate_01", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"account": "candidate@example.com", "password": "safe-password-123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    profile_response = await client.get("/api/v1/users/me", headers=headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["solved_count"] == 0

    update_response = await client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"nickname": "冲刺大厂", "bio": "专注 ACM 输入输出训练"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["nickname"] == "冲刺大厂"

    logout_response = await client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 204

    revoked_response = await client.get("/api/v1/users/me", headers=headers)
    assert revoked_response.status_code == 401
