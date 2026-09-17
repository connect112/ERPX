"""
API tests for employee self-service leave (modules/leave/routes.py's
/types/me, /applications/me, /applications/{id}/cancel/me, /balances/me).

Before these, POST /leave/applications required the RBAC permission
leave.applications.apply even to apply for your *own* leave — meaning no
employee, of any designation, could ever self-apply without an explicit
admin/HR-granted permission. These are ownership-gated instead, the same
"owning the record is the authorization" pattern as every other *.me
self-service route in this codebase.
"""

import uuid
from datetime import date, timedelta

import pytest

from modules.employees.repository import EmployeeRepository
from modules.leave.repository import LeaveTypeRepository

pytestmark = pytest.mark.api


async def _create_employee_with_login(client, db_session, organization, full_name="Test Employee"):
    unique = uuid.uuid4().hex[:8]
    email = f"employee.{unique}@erpx.example.com"
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

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return employee, {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def leave_type(db_session, organization):
    unique = uuid.uuid4().hex[:8]
    return await LeaveTypeRepository(db_session).create(
        organization_id=organization.id,
        name=f"Casual Leave {unique}",
        code=f"CL{unique}",
        annual_quota=12,
    )


async def test_employee_can_list_active_leave_types(client, db_session, organization, leave_type):
    _employee, headers = await _create_employee_with_login(client, db_session, organization)

    resp = await client.get("/api/v1/leave/types/me", headers=headers)
    assert resp.status_code == 200, resp.text
    assert leave_type.id in {uuid.UUID(t["id"]) for t in resp.json()}


async def test_employee_can_apply_for_own_leave_with_no_permissions(
    client, db_session, organization, leave_type
):
    _employee, headers = await _create_employee_with_login(client, db_session, organization)

    resp = await client.post(
        "/api/v1/leave/applications/me",
        json={
            "leave_type_id": str(leave_type.id),
            "start_date": str(date.today() + timedelta(days=5)),
            "end_date": str(date.today() + timedelta(days=6)),
            "reason": "Family function",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["employee_id"] == str(_employee.id)
    assert resp.json()["status"] == "pending"


async def test_employee_cannot_apply_leave_for_someone_else(
    client, db_session, organization, leave_type
):
    """LeaveApplicationSelfCreateRequest has no employee_id field at all —
    the applied-for employee is always the caller's own, resolved via
    get_current_employee, never something the client can override."""
    _employee, headers = await _create_employee_with_login(client, db_session, organization)

    resp = await client.post(
        "/api/v1/leave/applications/me",
        json={
            "leave_type_id": str(leave_type.id),
            "start_date": str(date.today() + timedelta(days=5)),
            "end_date": str(date.today() + timedelta(days=6)),
            "reason": "Family function",
            "employee_id": str(uuid.uuid4()),
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["employee_id"] == str(_employee.id)


async def test_employee_sees_own_applications_and_can_cancel(
    client, db_session, organization, leave_type
):
    employee, headers = await _create_employee_with_login(client, db_session, organization)

    create_resp = await client.post(
        "/api/v1/leave/applications/me",
        json={
            "leave_type_id": str(leave_type.id),
            "start_date": str(date.today() + timedelta(days=5)),
            "end_date": str(date.today() + timedelta(days=6)),
            "reason": "Family function",
        },
        headers=headers,
    )
    application_id = create_resp.json()["id"]

    list_resp = await client.get("/api/v1/leave/applications/me", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    assert [a["id"] for a in list_resp.json()["items"]] == [application_id]

    cancel_resp = await client.post(
        f"/api/v1/leave/applications/{application_id}/cancel/me", headers=headers
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["status"] == "cancelled"


async def test_employee_cannot_cancel_another_employees_application(
    client, db_session, organization, leave_type
):
    employee_a, headers_a = await _create_employee_with_login(
        client, db_session, organization, full_name="Employee A"
    )
    _employee_b, headers_b = await _create_employee_with_login(
        client, db_session, organization, full_name="Employee B"
    )

    create_resp = await client.post(
        "/api/v1/leave/applications/me",
        json={
            "leave_type_id": str(leave_type.id),
            "start_date": str(date.today() + timedelta(days=5)),
            "end_date": str(date.today() + timedelta(days=6)),
            "reason": "Family function",
        },
        headers=headers_a,
    )
    application_id = create_resp.json()["id"]

    cancel_resp = await client.post(
        f"/api/v1/leave/applications/{application_id}/cancel/me", headers=headers_b
    )
    # 404, not 403: employee B shouldn't be able to tell employee A's
    # leave application exists at all.
    assert cancel_resp.status_code == 404, cancel_resp.text


async def test_employee_can_view_own_leave_balance(client, db_session, organization, leave_type):
    _employee, headers = await _create_employee_with_login(client, db_session, organization)

    resp = await client.get(
        f"/api/v1/leave/balances/me?year={date.today().year}", headers=headers
    )
    assert resp.status_code == 200, resp.text
    balances = {b["leave_type_id"]: b for b in resp.json()}
    assert str(leave_type.id) in balances
    assert balances[str(leave_type.id)]["balance"] == leave_type.annual_quota
