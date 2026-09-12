"""
API tests for the employee self-service invite flow, in particular the
designation -> access auto-linking added alongside migration 0041: a
Designation's linked_role_id and grants_trainer_access should carry
through EmployeeService.invite_employee into a real RBAC role grant and/or
a real Trainer record, driven purely by which designation the invited
employee holds.
"""

import pytest

from modules.authorization.repository import AuthorizationRepository
from modules.trainers.repository import TrainerRepository

pytestmark = pytest.mark.api

_EMPLOYEE_PAYLOAD = {
    "full_name": "Asha Verma",
    "email": "asha.verma@example.com",
    "phone": "+91-9000000000",
    "gender": "female",
    "date_of_birth": "1995-04-12",
    "address_line1": "221B Baker Street",
    "city": "Bengaluru",
    "state": "Karnataka",
    "country": "India",
    "postal_code": "560001",
    "emergency_contact_name": "Rahul Verma",
    "emergency_contact_phone": "+91-9111111111",
    "employment_type": "full_time",
    "date_of_joining": "2026-01-15",
}


async def _create_department_and_designation(client, auth_headers, **designation_overrides):
    dept_resp = await client.post(
        "/api/v1/hr/departments",
        json={"name": "Security Delivery", "code": "SECD"},
        headers=auth_headers,
    )
    assert dept_resp.status_code == 201, dept_resp.text
    department = dept_resp.json()

    designation_payload = {
        "title": "Information Security Engineer",
        "code": "ISE",
        **designation_overrides,
    }
    designation_resp = await client.post(
        "/api/v1/hr/designations", json=designation_payload, headers=auth_headers
    )
    assert designation_resp.status_code == 201, designation_resp.text
    return department, designation_resp.json()


async def test_invite_employee_grants_linked_role_and_trainer_access(
    client, auth_headers, db_session, rbac_seeded
):
    authz_repo = AuthorizationRepository(db_session)
    staff_role = await authz_repo.get_role_by_slug("staff")
    assert staff_role is not None

    department, designation = await _create_department_and_designation(
        client,
        auth_headers,
        linked_role_id=str(staff_role.id),
        grants_trainer_access=True,
    )
    assert designation["linked_role_id"] == str(staff_role.id)
    assert designation["grants_trainer_access"] is True

    create_resp = await client.post(
        "/api/v1/employees",
        json={
            **_EMPLOYEE_PAYLOAD,
            "department_id": department["id"],
            "designation_id": designation["id"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    employee = create_resp.json()
    assert employee["user_id"] is None

    invite_resp = await client.post(
        f"/api/v1/employees/{employee['id']}/invite", headers=auth_headers
    )
    assert invite_resp.status_code == 200, invite_resp.text
    invited = invite_resp.json()
    user_id = invited["user_id"]
    assert user_id is not None

    # The linked role was actually granted, not just accepted on the
    # designation — assign_role's own effect, not merely that the call
    # didn't raise.
    user_roles = await authz_repo.get_roles_for_user(user_id)
    assert any(str(r.id) == str(staff_role.id) for r in user_roles)

    # grants_trainer_access actually created the Trainer row that
    # trainer-portal login depends on (see modules/trainers/dependencies.py's
    # User -> Employee -> Trainer resolution chain).
    trainer_repo = TrainerRepository(db_session)
    trainer = await trainer_repo.get_by_employee_id(employee["id"], department["organization_id"])
    assert trainer is not None


async def test_invite_employee_with_bare_designation_grants_no_extra_access(
    client, auth_headers, db_session, rbac_seeded
):
    """A designation with neither linked_role_id nor grants_trainer_access
    set (the common case — most job titles grant nothing beyond the basic
    employee-portal login every employee gets regardless) shouldn't create
    a Trainer row or assign any role."""
    department, designation = await _create_department_and_designation(client, auth_headers)
    assert designation["linked_role_id"] is None
    assert designation["grants_trainer_access"] is False

    create_resp = await client.post(
        "/api/v1/employees",
        json={
            **_EMPLOYEE_PAYLOAD,
            "email": "no-extra-access@example.com",
            "department_id": department["id"],
            "designation_id": designation["id"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    employee = create_resp.json()

    invite_resp = await client.post(
        f"/api/v1/employees/{employee['id']}/invite", headers=auth_headers
    )
    assert invite_resp.status_code == 200, invite_resp.text
    user_id = invite_resp.json()["user_id"]

    authz_repo = AuthorizationRepository(db_session)
    user_roles = await authz_repo.get_roles_for_user(user_id)
    assert user_roles == []

    trainer_repo = TrainerRepository(db_session)
    trainer = await trainer_repo.get_by_employee_id(employee["id"], department["organization_id"])
    assert trainer is None


async def test_designation_rejects_linking_super_admin_role(client, auth_headers, rbac_seeded):
    """The blocklist in modules/hr/service.py's _validate_linked_role is
    what stands between a designation and silently mass-granting the
    platform's most powerful role — assert it's actually enforced over
    the API, not just present in code."""
    authz_repo_resp = await client.get("/api/v1/authorization/roles", headers=auth_headers)
    assert authz_repo_resp.status_code == 200
    super_admin = next(r for r in authz_repo_resp.json() if r["slug"] == "super_admin")

    resp = await client.post(
        "/api/v1/hr/designations",
        json={
            "title": "Should Not Work",
            "code": "SNW",
            "linked_role_id": super_admin["id"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text
