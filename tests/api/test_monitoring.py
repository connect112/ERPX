"""
API tests for the Monitoring module: real health checks against the
actual running database/storage/redis, plus real platform counts. No
persistence layer to seed — every assertion is against a live check.
"""

import pytest

pytestmark = pytest.mark.api


async def test_staff_without_permission_cannot_view_health(client, staff_headers):
    response = await client.get("/api/v1/monitoring/health", headers=staff_headers)
    assert response.status_code == 403


async def test_staff_without_permission_cannot_view_stats(client, staff_headers):
    response = await client.get("/api/v1/monitoring/stats", headers=staff_headers)
    assert response.status_code == 403


async def test_health_check_reports_real_database_and_storage(client, auth_headers):
    response = await client.get("/api/v1/monitoring/health", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    components = {c["component"]: c for c in body["checks"]}
    assert set(components.keys()) == {"database", "storage", "redis"}

    assert components["database"]["status"] == "healthy"
    assert components["database"]["latency_ms"] is not None
    assert "connections" in components["database"]["detail"]

    assert components["storage"]["status"] == "healthy"
    assert components["storage"]["latency_ms"] is not None

    assert components["redis"]["status"] in {"healthy", "unhealthy"}

    assert body["overall_status"] in {"healthy", "degraded"}


async def test_platform_stats_reflect_real_counts(client, auth_headers):
    response = await client.get("/api/v1/monitoring/stats", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["organization_count"] >= 1
    assert body["user_count"] >= 1
    assert body["student_count"] >= 0
    assert body["audit_events_last_24h"] >= 0
