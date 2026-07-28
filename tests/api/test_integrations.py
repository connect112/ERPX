"""
API tests for the Integrations module: a config registry plus a real
connection test (an actual outbound HTTP request to the configured
base_url, not a simulated result). The success case points at the local
MinIO health endpoint (already running for this test session — see
tests/README.md); the failure case points at a port nothing listens on,
so both are genuine, deterministic real network outcomes.
"""

import pytest

pytestmark = pytest.mark.api


async def _create_integration(client, auth_headers, **overrides):
    payload = {
        "provider": "custom",
        "name": "Internal health check",
        "base_url": "http://127.0.0.1:9000/minio/health/live",
        "api_key": "sk-test-1234567890abcd",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/integrations", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_integration_masks_api_key(client, auth_headers):
    integration = await _create_integration(client, auth_headers)
    assert integration["masked_api_key"] == "****abcd"
    assert "api_key" not in integration


async def test_staff_without_permission_cannot_manage_integrations(client, staff_headers):
    response = await client.post(
        "/api/v1/integrations",
        json={"provider": "custom", "name": "x", "base_url": "http://example.invalid"},
        headers=staff_headers,
    )
    assert response.status_code == 403


async def test_connection_test_records_real_success(client, auth_headers):
    integration = await _create_integration(client, auth_headers)

    response = await client.post(
        f"/api/v1/integrations/{integration['id']}/test", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["last_test_status"] == "success"
    assert body["last_tested_at"] is not None
    assert "200" in body["last_test_message"]


async def test_connection_test_records_real_failure(client, auth_headers):
    integration = await _create_integration(
        client, auth_headers, base_url="http://127.0.0.1:1/unreachable"
    )

    response = await client.post(
        f"/api/v1/integrations/{integration['id']}/test", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["last_test_status"] == "failed"
    assert body["last_test_message"]


async def test_list_and_delete_integration(client, auth_headers):
    integration = await _create_integration(client, auth_headers)

    list_response = await client.get("/api/v1/integrations", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(i["id"] == integration["id"] for i in list_response.json()["items"])

    delete_response = await client.delete(f"/api/v1/integrations/{integration['id']}", headers=auth_headers)
    assert delete_response.status_code == 200

    get_response = await client.get(f"/api/v1/integrations/{integration['id']}", headers=auth_headers)
    assert get_response.status_code == 404
