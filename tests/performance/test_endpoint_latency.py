"""
Latency-regression tests for representative endpoints.

These run over the same in-process ASGI transport as `tests/api` (real
FastAPI app, real Postgres, no network hop), so absolute numbers are not
comparable to a deployed environment — the point is to catch *regressions*
within this app: an accidental N+1 query, a missing index, an unbounded
loop. Budgets are generous on purpose to avoid flaking on a loaded dev
machine or CI runner; a real regression blows past them by a wide margin,
not by a few milliseconds.
"""

import time

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.performance

ITERATIONS = 10


async def _measure(coro_factory) -> list[float]:
    """Runs `coro_factory()` `ITERATIONS` times, returning latencies in ms."""
    samples: list[float] = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        await coro_factory()
        samples.append((time.perf_counter() - start) * 1000)
    return samples


def _assert_budget(samples: list[float], *, mean_ms: float, max_ms: float, label: str) -> None:
    mean = sum(samples) / len(samples)
    worst = max(samples)
    assert mean < mean_ms, f"{label}: mean latency {mean:.1f}ms exceeded budget {mean_ms}ms ({samples})"
    assert worst < max_ms, f"{label}: worst latency {worst:.1f}ms exceeded budget {max_ms}ms ({samples})"


async def test_health_endpoint_latency(client: AsyncClient):
    async def call():
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    samples = await _measure(call)
    _assert_budget(samples, mean_ms=100, max_ms=300, label="GET /health")


async def test_login_latency(client: AsyncClient, db_session):
    from modules.authentication.repository import AuthRepository

    payload = {
        "email": "perf.login@erpx.example.com",
        "password": "StrongPass1!",
        "full_name": "Perf Login User",
    }
    register_response = await client.post("/api/v1/auth/register", json=payload)
    assert register_response.status_code == 201

    user = await AuthRepository(db_session).get_user_by_email(payload["email"])
    await AuthRepository(db_session).mark_email_verified(user)

    async def call():
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
        assert response.status_code == 200

    samples = await _measure(call)
    # bcrypt's hash-verification cost dominates this endpoint by design (it's
    # deliberately slow to resist brute-forcing) and varies a lot with host
    # CPU load, so this budget is wide — it's here to catch a regression
    # stacked on top of bcrypt (e.g. an accidental extra query per attempt),
    # not to benchmark bcrypt itself.
    _assert_budget(samples, mean_ms=1000, max_ms=1800, label="POST /auth/login")


async def test_leads_list_latency(client: AsyncClient, auth_headers: dict):
    for i in range(25):
        response = await client.post(
            "/api/v1/crm/leads",
            json={"full_name": f"Perf Lead {i}", "email": f"perf.lead.{i}@example.com", "source": "website"},
            headers=auth_headers,
        )
        assert response.status_code == 201

    async def call():
        response = await client.get("/api/v1/crm/leads?limit=20", headers=auth_headers)
        assert response.status_code == 200

    samples = await _measure(call)
    _assert_budget(samples, mean_ms=250, max_ms=600, label="GET /crm/leads")


async def test_lead_create_latency(client: AsyncClient, auth_headers: dict):
    counter = {"n": 0}

    async def call():
        counter["n"] += 1
        response = await client.post(
            "/api/v1/crm/leads",
            json={
                "full_name": f"Create Perf {counter['n']}",
                "email": f"create.perf.{counter['n']}@example.com",
                "source": "referral",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201

    samples = await _measure(call)
    _assert_budget(samples, mean_ms=250, max_ms=600, label="POST /crm/leads")


async def test_dashboard_summary_latency(client: AsyncClient, auth_headers: dict):
    async def call():
        response = await client.get("/api/v1/dashboard/summary", headers=auth_headers)
        assert response.status_code == 200

    samples = await _measure(call)
    _assert_budget(samples, mean_ms=250, max_ms=600, label="GET /dashboard/summary")
