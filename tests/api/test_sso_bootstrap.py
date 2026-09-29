"""
API tests for cross-subdomain SSO: the `erpx_sso` cookie set at /login and
/refresh, and the /auth/sso/bootstrap endpoint that exchanges it for a
fresh token pair — see modules/authentication/routes.py. This is what lets
someone who logged in on one ERPX subdomain (erp./lms./staff./trainer.
pentrix.in) land on another already authenticated, no second login.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.security import TokenType, decode_token
from modules.authentication.repository import AuthRepository

pytestmark = pytest.mark.api

SSO_COOKIE_NAME = "erpx_sso"


@pytest.fixture
def register_payload():
    return {
        "email": "sso.user@erpx.example.com",
        "password": "StrongPass1!",
        "full_name": "SSO User",
    }


async def _register_and_verify(client, db_session, register_payload):
    await client.post("/api/v1/auth/register", json=register_payload)
    user = await AuthRepository(db_session).get_user_by_email(register_payload["email"])
    await AuthRepository(db_session).mark_email_verified(user)


async def test_login_does_not_set_sso_cookie_when_disabled(client, db_session, register_payload):
    """Default (local dev / every other test): SSO_COOKIE_DOMAIN is unset, so
    the whole feature is a no-op and existing login behavior is untouched."""
    assert settings.SSO_COOKIE_DOMAIN == ""
    await _register_and_verify(client, db_session, register_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert response.status_code == 200
    assert SSO_COOKIE_NAME not in response.cookies


async def test_login_sets_sso_cookie_when_enabled(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "SSO_COOKIE_DOMAIN", "testserver")
    await _register_and_verify(client, db_session, register_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert response.status_code == 200
    assert response.cookies[SSO_COOKIE_NAME] == response.json()["refresh_token"]


async def test_sso_cookie_has_no_persistent_max_age(client, db_session, register_payload, monkeypatch):
    """Deliberately a browser-session cookie (no Max-Age/Expires attribute)
    so it's gone once the browser is fully closed, unlike the actual login
    session — see _set_sso_cookie's docstring. A shared/reused device
    silently signing in as whoever last used it should not survive that."""
    monkeypatch.setattr(settings, "SSO_COOKIE_DOMAIN", "testserver")
    await _register_and_verify(client, db_session, register_payload)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "max-age" not in set_cookie_header.lower()
    assert "expires" not in set_cookie_header.lower()


async def test_bootstrap_without_cookie_is_unauthorized(client, monkeypatch):
    monkeypatch.setattr(settings, "SSO_COOKIE_DOMAIN", "testserver")
    response = await client.post("/api/v1/auth/sso/bootstrap")
    assert response.status_code == 401


async def test_bootstrap_rejects_a_garbage_cookie(client, monkeypatch):
    monkeypatch.setattr(settings, "SSO_COOKIE_DOMAIN", "testserver")
    response = await client.post(
        "/api/v1/auth/sso/bootstrap", cookies={SSO_COOKIE_NAME: "not-a-real-token"}
    )
    assert response.status_code == 401


async def test_bootstrap_exchanges_cookie_for_a_fresh_session(
    client, db_session, register_payload, monkeypatch
):
    """
    The actual scenario this exists for: someone logs in on one ERPX
    subdomain, then a *different* origin (nothing in its own localStorage)
    presents only the shared cookie. Bootstrap must stand up a full session
    — including the user profile — from that cookie alone, and rotate it
    exactly like a normal refresh does.
    """
    monkeypatch.setattr(settings, "SSO_COOKIE_DOMAIN", "testserver")
    await _register_and_verify(client, db_session, register_payload)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    session_cookie = login_response.cookies[SSO_COOKIE_NAME]

    bootstrap_response = await client.post(
        "/api/v1/auth/sso/bootstrap", cookies={SSO_COOKIE_NAME: session_cookie}
    )
    assert bootstrap_response.status_code == 200
    body = bootstrap_response.json()
    assert body["access_token"]
    assert body["user"]["email"] == register_payload["email"]
    # Rotated, same as /refresh — bootstrap must not just echo the cookie back.
    assert body["refresh_token"] != session_cookie
    assert bootstrap_response.cookies[SSO_COOKIE_NAME] == body["refresh_token"]

    me_response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == register_payload["email"]


async def test_bootstrap_rejects_a_revoked_cookie(client, db_session, register_payload, monkeypatch):
    """A cookie already exchanged once (or logged out) must not work twice —
    same reuse-detection guarantee /refresh already has."""
    monkeypatch.setattr(settings, "SSO_COOKIE_DOMAIN", "testserver")
    await _register_and_verify(client, db_session, register_payload)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    session_cookie = login_response.cookies[SSO_COOKIE_NAME]

    first = await client.post("/api/v1/auth/sso/bootstrap", cookies={SSO_COOKIE_NAME: session_cookie})
    assert first.status_code == 200

    reused = await client.post("/api/v1/auth/sso/bootstrap", cookies={SSO_COOKIE_NAME: session_cookie})
    assert reused.status_code == 401


async def _backdate_refresh_token(db_session, repo: AuthRepository, raw_token: str, age: timedelta) -> None:
    """Directly ages a refresh token's `created_at` in the DB, rather than
    racing the wall clock with a near-zero SSO_BRIDGE_MAX_AGE_HOURS (which
    is exactly as flaky as it sounds — the created_at write and the check
    can land in the same microsecond)."""
    payload = decode_token(raw_token, TokenType.REFRESH)
    token_row = await repo.get_refresh_token(payload["jti"])
    token_row.created_at = datetime.now(timezone.utc) - age
    await db_session.flush()


async def test_bootstrap_rejects_a_cookie_older_than_the_bridge_max_age(
    client, db_session, register_payload, monkeypatch
):
    """Defense in depth for a browser that restores its session across a
    restart despite the cookie carrying no Max-Age: even a technically
    still-active, non-revoked token must not silently bridge into a
    different subdomain once it's older than SSO_BRIDGE_MAX_AGE_HOURS.
    Found live: a shared/reused test browser silently signed someone into
    a stale account days after that account last explicitly used it."""
    monkeypatch.setattr(settings, "SSO_COOKIE_DOMAIN", "testserver")
    assert settings.SSO_BRIDGE_MAX_AGE_HOURS == 24
    await _register_and_verify(client, db_session, register_payload)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    session_cookie = login_response.cookies[SSO_COOKIE_NAME]
    await _backdate_refresh_token(db_session, AuthRepository(db_session), session_cookie, timedelta(hours=25))

    response = await client.post("/api/v1/auth/sso/bootstrap", cookies={SSO_COOKIE_NAME: session_cookie})
    assert response.status_code == 401


async def test_refresh_is_not_subject_to_the_sso_bridge_max_age(
    client, db_session, register_payload, monkeypatch
):
    """The bridge age cap only applies to sso_bootstrap — a token being too
    old to silently jump to a *different* subdomain says nothing about its
    validity for a normal refresh on the portal it was actually issued on."""
    monkeypatch.setattr(settings, "SSO_COOKIE_DOMAIN", "testserver")
    assert settings.SSO_BRIDGE_MAX_AGE_HOURS == 24
    await _register_and_verify(client, db_session, register_payload)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    refresh_token = login_response.json()["refresh_token"]
    await _backdate_refresh_token(db_session, AuthRepository(db_session), refresh_token, timedelta(hours=25))

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200


async def test_logout_clears_sso_cookie(client, db_session, register_payload, monkeypatch):
    monkeypatch.setattr(settings, "SSO_COOKIE_DOMAIN", "testserver")
    await _register_and_verify(client, db_session, register_payload)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    tokens = login_response.json()

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout_response.status_code == 200
    # An emptied/expired Set-Cookie is how a cookie gets cleared client-side.
    assert SSO_COOKIE_NAME in logout_response.headers.get("set-cookie", "")
