"""
API tests for per-route rate limiting on the pre-authentication surface of
the Authentication module (register/login/refresh/forgot-password/
reset-password/resend-verification) — the endpoints an anonymous attacker
can reach without ever holding a valid credential, and therefore the ones
that actually benefit from a budget tighter than the platform-wide
`RATE_LIMIT_DEFAULT` (100/minute, shared with every read-only endpoint too).

The shared `Limiter` (`app/core/limiter.py`) is a process-wide singleton
reused across the whole test session (`tests/_fixtures.py` imports the
real `app` once). Its `client` fixture already resets the limiter's
storage before every test specifically so unrelated tests (register/login
are exercised as ordinary setup machinery across many other test files)
never inherit hit counts from each other — that reset is what lets this
file deliberately exhaust each limit from a clean slate below without
poisoning the budget for tests that run afterward.
"""

import pytest

pytestmark = pytest.mark.api


async def test_login_is_rate_limited_after_ten_requests_per_minute(client):
    payload = {"email": "nobody@erpx.example.com", "password": "wrong-password"}

    for _ in range(10):
        response = await client.post("/api/v1/auth/login", json=payload)
        assert response.status_code != 429

    eleventh = await client.post("/api/v1/auth/login", json=payload)
    assert eleventh.status_code == 429


async def test_register_is_rate_limited_after_ten_requests_per_minute(client):
    for i in range(10):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"rl-register-{i}@erpx.example.com",
                "password": "StrongPass1!",
                "full_name": "Rate Limit Test",
            },
        )
        assert response.status_code != 429

    eleventh = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rl-register-overflow@erpx.example.com",
            "password": "StrongPass1!",
            "full_name": "Rate Limit Test",
        },
    )
    assert eleventh.status_code == 429


async def test_forgot_password_is_rate_limited_after_five_requests_per_minute(client):
    payload = {"email": "nobody@erpx.example.com"}

    for _ in range(5):
        response = await client.post("/api/v1/auth/forgot-password", json=payload)
        assert response.status_code != 429

    sixth = await client.post("/api/v1/auth/forgot-password", json=payload)
    assert sixth.status_code == 429


async def test_rate_limit_is_scoped_per_route_not_global(client):
    """
    Exhausting /login's budget must not affect /forgot-password's separate
    budget — each `@limiter.limit(...)` decorator tracks its own route key,
    it isn't one shared counter across the whole auth module.
    """
    login_payload = {"email": "nobody@erpx.example.com", "password": "wrong-password"}
    for _ in range(10):
        await client.post("/api/v1/auth/login", json=login_payload)
    exhausted = await client.post("/api/v1/auth/login", json=login_payload)
    assert exhausted.status_code == 429

    still_available = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@erpx.example.com"}
    )
    assert still_available.status_code != 429


async def test_unlimited_endpoints_unaffected_by_auth_rate_limits(client):
    """/me (an authenticated, non-pre-auth endpoint) was never given a
    per-route limit by this change and must still only be bound by the
    platform-wide default — a 401 (no token) is expected, not a 429."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
