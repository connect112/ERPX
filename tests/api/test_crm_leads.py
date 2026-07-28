"""
API tests for CRM Leads — a representative flat business module: create,
list, update, status-transition validation, and soft delete.
"""

import pytest

pytestmark = pytest.mark.api


async def _create_lead(client, auth_headers, **overrides):
    payload = {
        "full_name": "Jordan Smith",
        "email": "jordan.smith@example.com",
        "phone": "+1-555-0100",
        "source": "website",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/crm/leads", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_lead(client, auth_headers):
    lead = await _create_lead(client, auth_headers)
    assert lead["full_name"] == "Jordan Smith"
    assert lead["status"] == "new"
    assert lead["source"] == "website"


async def test_list_leads_includes_created_lead(client, auth_headers):
    created = await _create_lead(client, auth_headers, full_name="List Me")

    response = await client.get("/api/v1/crm/leads", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(item["id"] == created["id"] for item in body["items"])


async def test_get_lead_by_id(client, auth_headers):
    created = await _create_lead(client, auth_headers)

    response = await client.get(f"/api/v1/crm/leads/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_nonexistent_lead_returns_404(client, auth_headers):
    response = await client.get(
        "/api/v1/crm/leads/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 404


async def test_update_lead(client, auth_headers):
    created = await _create_lead(client, auth_headers)

    response = await client.patch(
        f"/api/v1/crm/leads/{created['id']}", json={"notes": "Called, interested"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["notes"] == "Called, interested"


async def test_valid_status_transition_succeeds(client, auth_headers):
    created = await _create_lead(client, auth_headers)

    response = await client.post(
        f"/api/v1/crm/leads/{created['id']}/status", json={"status": "contacted"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "contacted"


async def test_invalid_status_transition_is_rejected(client, auth_headers):
    """A NEW lead cannot jump straight to CONVERTED — only via QUALIFIED first."""
    created = await _create_lead(client, auth_headers)

    response = await client.post(
        f"/api/v1/crm/leads/{created['id']}/status", json={"status": "converted"}, headers=auth_headers
    )
    assert response.status_code == 422


async def test_marking_lost_requires_a_reason(client, auth_headers):
    created = await _create_lead(client, auth_headers)

    response = await client.post(
        f"/api/v1/crm/leads/{created['id']}/status", json={"status": "lost"}, headers=auth_headers
    )
    assert response.status_code == 422

    with_reason = await client.post(
        f"/api/v1/crm/leads/{created['id']}/status",
        json={"status": "lost", "lost_reason": "Budget constraints"},
        headers=auth_headers,
    )
    assert with_reason.status_code == 200
    assert with_reason.json()["status"] == "lost"


async def test_delete_lead_soft_deletes_it(client, auth_headers):
    created = await _create_lead(client, auth_headers)

    delete_response = await client.delete(f"/api/v1/crm/leads/{created['id']}", headers=auth_headers)
    assert delete_response.status_code == 200

    get_response = await client.get(f"/api/v1/crm/leads/{created['id']}", headers=auth_headers)
    assert get_response.status_code == 404
