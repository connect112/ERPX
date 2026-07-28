"""
API tests for the Audit module — verifies the automatic SQLAlchemy-event
capture in `modules.audit.hooks` actually produces rows for real business
operations (not just that the audit endpoints exist), and that access is
restricted to users holding `audit.view`.
"""

import pytest

pytestmark = pytest.mark.api


@pytest.fixture
def register_payload():
    return {
        "email": "audit.new.user@erpx.example.com",
        "password": "StrongPass1!",
        "full_name": "Audit New User",
    }


async def test_creating_a_lead_produces_a_create_audit_entry(client, auth_headers):
    response = await client.post(
        "/api/v1/crm/leads",
        json={"full_name": "Audited Lead", "email": "audited.lead@example.com", "source": "website"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    lead_id = response.json()["id"]

    logs_response = await client.get(
        f"/api/v1/audit?entity_type=crm_leads&entity_id={lead_id}", headers=auth_headers
    )
    assert logs_response.status_code == 200
    body = logs_response.json()
    assert body["total"] >= 1
    entry = body["items"][0]
    assert entry["action"] == "create"
    assert entry["entity_type"] == "crm_leads"
    assert entry["entity_id"] == lead_id
    assert entry["changes"]["full_name"] == "Audited Lead"


async def test_updating_a_lead_produces_an_update_audit_entry_with_diff(client, auth_headers):
    create_response = await client.post(
        "/api/v1/crm/leads",
        json={"full_name": "Before Update", "email": "before.update@example.com", "source": "website"},
        headers=auth_headers,
    )
    lead_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/crm/leads/{lead_id}", json={"notes": "Called, interested"}, headers=auth_headers
    )
    assert update_response.status_code == 200

    logs_response = await client.get(
        f"/api/v1/audit?entity_type=crm_leads&entity_id={lead_id}&action=update", headers=auth_headers
    )
    body = logs_response.json()
    assert body["total"] >= 1
    entry = body["items"][0]
    assert entry["action"] == "update"
    assert entry["changes"]["notes"]["new"] == "Called, interested"


async def test_audit_entry_records_the_acting_user(client, auth_headers, superuser):
    user, _ = superuser
    await client.post(
        "/api/v1/crm/leads",
        json={"full_name": "Attributed Lead", "email": "attributed.lead@example.com", "source": "website"},
        headers=auth_headers,
    )

    logs_response = await client.get(
        f"/api/v1/audit?entity_type=crm_leads&user_id={user.id}", headers=auth_headers
    )
    body = logs_response.json()
    assert body["total"] >= 1
    assert body["items"][0]["user_id"] == str(user.id)
    assert body["items"][0]["user_email"] == user.email


async def test_password_hash_is_never_captured_in_audit_changes(client, register_payload, db_session):
    from sqlalchemy import select

    from modules.audit.models import AuditLog

    await client.post("/api/v1/auth/register", json=register_payload)

    result = await db_session.execute(select(AuditLog).where(AuditLog.entity_type == "users"))
    user_audit_rows = result.scalars().all()
    assert len(user_audit_rows) >= 1
    for row in user_audit_rows:
        assert "hashed_password" not in row.changes
        assert "two_factor_secret" not in row.changes


async def test_sensitive_token_tables_are_never_audited(client, register_payload, db_session):
    from sqlalchemy import select

    from modules.audit.models import AuditLog

    await client.post("/api/v1/auth/register", json=register_payload)

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_type == "email_verification_tokens")
    )
    assert result.scalar_one_or_none() is None


async def test_staff_user_without_audit_permission_is_forbidden(client, staff_headers):
    response = await client.get("/api/v1/audit", headers=staff_headers)
    assert response.status_code == 403


async def test_soft_deleting_a_lead_produces_an_update_audit_entry(client, auth_headers):
    # CRM Leads are soft-deleted (`deleted_at` set via UPDATE, not a real SQL
    # DELETE), so the resulting audit action is "update", not "delete" —
    # this exercises that the hook correctly reflects what actually
    # happened at the database level rather than what the HTTP verb implies.
    create_response = await client.post(
        "/api/v1/crm/leads",
        json={"full_name": "To Delete", "email": "to.delete@example.com", "source": "website"},
        headers=auth_headers,
    )
    lead_id = create_response.json()["id"]

    delete_response = await client.delete(f"/api/v1/crm/leads/{lead_id}", headers=auth_headers)
    assert delete_response.status_code == 200

    logs_response = await client.get(
        f"/api/v1/audit?entity_type=crm_leads&entity_id={lead_id}&action=update", headers=auth_headers
    )
    body = logs_response.json()
    matching = [e for e in body["items"] if "deleted_at" in e["changes"]]
    assert len(matching) >= 1
    assert matching[0]["changes"]["deleted_at"]["old"] is None
    assert matching[0]["changes"]["deleted_at"]["new"] is not None


async def test_hard_deleting_a_branch_produces_a_delete_audit_entry(client, auth_headers, organization):
    create_response = await client.post(
        "/api/v1/branches",
        json={"organization_id": str(organization.id), "name": "Temp Branch", "code": "TMP01"},
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    branch_id = create_response.json()["id"]

    delete_response = await client.delete(f"/api/v1/branches/{branch_id}", headers=auth_headers)
    assert delete_response.status_code == 200

    logs_response = await client.get(
        f"/api/v1/audit?entity_type=branches&entity_id={branch_id}&action=delete", headers=auth_headers
    )
    body = logs_response.json()
    assert body["total"] >= 1
    assert body["items"][0]["changes"]["code"] == "TMP01"
