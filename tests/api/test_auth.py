"""
API tests for the Authentication module: registration, email-verification
gating, login, /me, and token refresh — the security-critical path every
other module's protected endpoints depend on.
"""

import pytest

from modules.authentication.repository import AuthRepository

pytestmark = pytest.mark.api


@pytest.fixture
def register_payload():
    return {
        "email": "new.user@erpx.example.com",
        "password": "StrongPass1!",
        "full_name": "New User",
    }


async def test_register_creates_pending_verification_user(client, register_payload):
    response = await client.post("/api/v1/auth/register", json=register_payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == register_payload["email"]
    assert body["is_email_verified"] is False
    assert "password" not in body
    assert "hashed_password" not in body


async def test_register_duplicate_email_rejected(client, register_payload):
    first = await client.post("/api/v1/auth/register", json=register_payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=register_payload)
    assert second.status_code == 409


async def test_register_rejects_weak_password(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@erpx.example.com", "password": "weak", "full_name": "Weak Pass"},
    )
    assert response.status_code == 422


async def test_login_before_email_verification_is_rejected(client, register_payload):
    await client.post("/api/v1/auth/register", json=register_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert response.status_code == 401


async def test_login_with_wrong_password_is_rejected(client, register_payload, db_session):
    await client.post("/api/v1/auth/register", json=register_payload)
    user = await AuthRepository(db_session).get_user_by_email(register_payload["email"])
    await AuthRepository(db_session).mark_email_verified(user)

    response = await client.post(
        "/api/v1/auth/login", json={"email": register_payload["email"], "password": "WrongPassword1!"}
    )
    assert response.status_code == 401


async def test_login_unknown_email_is_rejected(client):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@erpx.example.com", "password": "StrongPass1!"}
    )
    assert response.status_code == 401


async def test_full_register_verify_login_me_refresh_flow(client, register_payload, db_session):
    await client.post("/api/v1/auth/register", json=register_payload)
    user = await AuthRepository(db_session).get_user_by_email(register_payload["email"])
    await AuthRepository(db_session).mark_email_verified(user)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    me_response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == register_payload["email"]

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["access_token"]
    assert refreshed["access_token"] != tokens["access_token"]


async def test_me_without_token_is_unauthorized(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_garbage_token_is_unauthorized(client):
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


async def test_superuser_fixture_can_access_me(client, auth_headers):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "active"
