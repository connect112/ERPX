"""
API tests for the health/readiness/liveness endpoints.

`/health` never touches a dependency, so it's tested once for the trivial
"process is up" case. `/health/ready`'s dependency checkers
(`check_database`, `check_redis`, `check_storage`, `check_search`) are
monkeypatched individually rather than actually taking down Postgres/Redis/
MinIO/Elasticsearch — the thing under test is the readiness *policy*
(critical dependencies gate readiness, optional ones don't), not whether
each real client library can detect an outage, which is exercised for real
by modules/monitoring's own tests (tests/api/test_monitoring.py).
"""

import pytest

import app.api.v1.health as health_module

pytestmark = pytest.mark.api


async def _healthy() -> bool:
    return True


async def _unhealthy() -> bool:
    return False


async def test_liveness_never_checks_dependencies(client, monkeypatch):
    # Even if every dependency checker would report unhealthy, /health must
    # still return 200 — it's the liveness probe and must stay lightweight.
    monkeypatch.setattr(health_module, "check_database", _unhealthy)
    monkeypatch.setattr(health_module, "check_redis", _unhealthy)
    monkeypatch.setattr(health_module, "check_storage", _unhealthy)
    monkeypatch.setattr(health_module, "check_search", _unhealthy)

    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_readiness_when_all_dependencies_healthy(client, monkeypatch):
    monkeypatch.setattr(health_module, "check_database", _healthy)
    monkeypatch.setattr(health_module, "check_redis", _healthy)
    monkeypatch.setattr(health_module, "check_storage", _healthy)
    monkeypatch.setattr(health_module, "check_search", _healthy)

    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["ready"] is True
    assert body["live"] is True
    assert body["checks"]["database"] == {"healthy": True, "critical": True}
    assert body["checks"]["redis"] == {"healthy": True, "critical": False}
    assert body["checks"]["storage"] == {"healthy": True, "critical": False}
    assert body["checks"]["search"] == {"healthy": True, "critical": False}


async def test_readiness_survives_elasticsearch_unavailable(client, monkeypatch):
    """The regression test for the production-readiness audit's top finding:
    an Elasticsearch outage must NOT fail readiness, since nothing in the
    codebase actually depends on it yet."""
    monkeypatch.setattr(health_module, "check_database", _healthy)
    monkeypatch.setattr(health_module, "check_redis", _healthy)
    monkeypatch.setattr(health_module, "check_storage", _healthy)
    monkeypatch.setattr(health_module, "check_search", _unhealthy)

    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["ready"] is True
    assert body["checks"]["search"] == {"healthy": False, "critical": False}


async def test_readiness_fails_when_postgres_unavailable(client, monkeypatch):
    monkeypatch.setattr(health_module, "check_database", _unhealthy)
    monkeypatch.setattr(health_module, "check_redis", _healthy)
    monkeypatch.setattr(health_module, "check_storage", _healthy)
    monkeypatch.setattr(health_module, "check_search", _healthy)

    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["ready"] is False
    assert body["checks"]["database"] == {"healthy": False, "critical": True}


@pytest.mark.parametrize("optional_dependency", ["redis", "storage", "search"])
async def test_readiness_survives_any_single_optional_dependency_failing(
    client, monkeypatch, optional_dependency
):
    monkeypatch.setattr(health_module, "check_database", _healthy)
    monkeypatch.setattr(health_module, "check_redis", _healthy)
    monkeypatch.setattr(health_module, "check_storage", _healthy)
    monkeypatch.setattr(health_module, "check_search", _healthy)
    monkeypatch.setattr(health_module, f"check_{optional_dependency}", _unhealthy)

    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["checks"][optional_dependency]["healthy"] is False
    assert body["checks"][optional_dependency]["critical"] is False


async def test_readiness_fails_regardless_of_optional_dependencies_when_critical_fails(
    client, monkeypatch
):
    # Critical dependency down AND every optional dependency also down —
    # still a single, unambiguous 503, not a partial/degraded 200.
    monkeypatch.setattr(health_module, "check_database", _unhealthy)
    monkeypatch.setattr(health_module, "check_redis", _unhealthy)
    monkeypatch.setattr(health_module, "check_storage", _unhealthy)
    monkeypatch.setattr(health_module, "check_search", _unhealthy)

    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["ready"] is False
