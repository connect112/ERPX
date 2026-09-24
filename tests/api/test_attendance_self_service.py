"""
API tests for employee self-service attendance (modules/attendance/routes.py's
/employee/check-in/me, /employee/check-out/me, /employee/me) — added
alongside the trainer-only /check-in/me, /check-out/me, /me routes so a
plain employee with no Trainer record (Accountant, HR, Ops staff — any
designation that doesn't grants_trainer_access) can also check themselves
in, not just trainers.
"""

import uuid
from datetime import date

import pytest

from modules.employees.repository import EmployeeRepository

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


async def test_employee_without_trainer_record_can_self_check_in_and_out(
    client, db_session, organization
):
    _employee, headers = await _create_employee_with_login(client, db_session, organization)

    check_in_resp = await client.post(
        "/api/v1/attendance/employee/check-in/me", json={}, headers=headers
    )
    assert check_in_resp.status_code == 201, check_in_resp.text
    assert check_in_resp.json()["check_in_time"]

    check_out_resp = await client.post(
        "/api/v1/attendance/employee/check-out/me", json={}, headers=headers
    )
    assert check_out_resp.status_code == 200, check_out_resp.text
    assert check_out_resp.json()["check_out_time"]

    list_resp = await client.get("/api/v1/attendance/employee/me", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    assert list_resp.json()["total"] == 1


async def test_employee_self_check_in_requires_no_permission(client, db_session, organization):
    """The whole point: a bare employee with zero RBAC permissions (no
    attendance.manage, nothing) can still check themselves in — ownership
    is the authorization, same as every other *.dependencies self-service
    dependency in this codebase."""
    _employee, headers = await _create_employee_with_login(client, db_session, organization)

    resp = await client.post("/api/v1/attendance/employee/check-in/me", json={}, headers=headers)
    assert resp.status_code == 201, resp.text


async def test_unlinked_user_cannot_self_check_in(client, db_session, organization):
    unique = uuid.uuid4().hex[:8]
    email = f"outsider.{unique}@erpx.example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "OutsiderPass1!", "full_name": "Outsider"},
    )
    from modules.authentication.repository import AuthRepository

    user = await AuthRepository(db_session).get_user_by_email(email)
    await AuthRepository(db_session).mark_email_verified(user)
    login_response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "OutsiderPass1!"}
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    resp = await client.post("/api/v1/attendance/employee/check-in/me", json={}, headers=headers)
    assert resp.status_code == 422, resp.text
