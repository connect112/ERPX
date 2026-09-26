"""API tests for employee expense reimbursement claims
(modules/expense_claims/routes.py) -- submission with a real receipt
upload (mirrors tests/api/test_documents.py's real two-phase MinIO
flow), and the admin approve/reject review workflow.
"""

import uuid
from datetime import date

import httpx
import pytest

from modules.employees.repository import EmployeeRepository

pytestmark = pytest.mark.api


async def _create_employee_with_login(client, db_session, organization, full_name="Expense Test Employee"):
    unique = uuid.uuid4().hex[:8]
    email = f"expense-employee.{unique}@erpx.example.com"
    password = "EmployeePass1!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register_response.status_code == 201

    from modules.authentication.repository import AuthRepository

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)

    from modules.users.repository import UserProfileRepository

    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    employee = await EmployeeRepository(db_session).create(
        organization_id=organization.id,
        user_id=user.id,
        full_name=full_name,
        date_of_joining=date(2024, 1, 1),
    )
    await db_session.flush()

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return employee, {"Authorization": f"Bearer {token}"}


async def _submit_claim_with_receipt(client, headers, description="Client dinner", amount=1250.50):
    presign_resp = await client.post(
        "/api/v1/expense-claims/me/receipts/presigned-upload",
        json={"filename": "receipt.jpg", "content_type": "image/jpeg"},
        headers=headers,
    )
    assert presign_resp.status_code == 200, presign_resp.text
    document_id = presign_resp.json()["document_id"]
    upload_url = presign_resp.json()["upload_url"]

    async with httpx.AsyncClient() as raw_client:
        put_resp = await raw_client.put(
            upload_url, content=b"fake receipt bytes", headers={"Content-Type": "image/jpeg"}
        )
        assert put_resp.status_code == 200, put_resp.text

    confirm_resp = await client.post(
        f"/api/v1/expense-claims/me/receipts/{document_id}/confirm", headers=headers
    )
    assert confirm_resp.status_code == 200, confirm_resp.text

    claim_resp = await client.post(
        "/api/v1/expense-claims/me",
        json={"description": description, "amount": amount, "receipt_document_id": document_id},
        headers=headers,
    )
    assert claim_resp.status_code == 201, claim_resp.text
    return claim_resp.json()


async def test_employee_can_submit_claim_with_receipt_and_see_it_pending(client, db_session, organization):
    _employee, headers = await _create_employee_with_login(client, db_session, organization)

    claim = await _submit_claim_with_receipt(client, headers)
    assert claim["status"] == "pending"
    assert claim["amount"] == 1250.50
    assert claim["receipt_document_id"] is not None

    today = date.today()
    assert claim["period_year"] == today.year
    assert claim["period_month"] == today.month

    list_resp = await client.get("/api/v1/expense-claims/me", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    assert list_resp.json()["total"] == 1


async def test_employee_cannot_submit_zero_or_negative_amount(client, db_session, organization):
    _employee, headers = await _create_employee_with_login(client, db_session, organization)
    resp = await client.post(
        "/api/v1/expense-claims/me",
        json={"description": "Bad claim", "amount": 0},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


async def test_admin_can_approve_a_pending_claim(client, auth_headers, db_session, organization):
    _employee, headers = await _create_employee_with_login(client, db_session, organization)
    claim = await _submit_claim_with_receipt(client, headers, description="Taxi fare", amount=450)

    approve_resp = await client.post(
        f"/api/v1/expense-claims/{claim['id']}/approve", headers=auth_headers
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["status"] == "approved"
    assert approve_resp.json()["reviewed_by_user_id"] is not None


async def test_admin_can_reject_a_pending_claim_with_a_reason(client, auth_headers, db_session, organization):
    _employee, headers = await _create_employee_with_login(client, db_session, organization)
    claim = await _submit_claim_with_receipt(client, headers, description="Suspicious claim", amount=99999)

    reject_resp = await client.post(
        f"/api/v1/expense-claims/{claim['id']}/reject",
        json={"rejection_reason": "No receipt attached matches this amount"},
        headers=auth_headers,
    )
    assert reject_resp.status_code == 200, reject_resp.text
    assert reject_resp.json()["status"] == "rejected"
    assert reject_resp.json()["rejection_reason"] == "No receipt attached matches this amount"


async def test_already_reviewed_claim_cannot_be_approved_again(client, auth_headers, db_session, organization):
    _employee, headers = await _create_employee_with_login(client, db_session, organization)
    claim = await _submit_claim_with_receipt(client, headers)

    first = await client.post(f"/api/v1/expense-claims/{claim['id']}/approve", headers=auth_headers)
    assert first.status_code == 200, first.text

    second = await client.post(f"/api/v1/expense-claims/{claim['id']}/approve", headers=auth_headers)
    assert second.status_code == 422, second.text


async def test_employee_without_permissions_cannot_approve_claims(client, db_session, organization):
    _employee, headers = await _create_employee_with_login(client, db_session, organization)
    claim = await _submit_claim_with_receipt(client, headers)

    resp = await client.post(f"/api/v1/expense-claims/{claim['id']}/approve", headers=headers)
    assert resp.status_code == 403, resp.text
