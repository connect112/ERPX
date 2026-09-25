"""
API tests for the employee self-service invite flow, in particular the
designation -> access auto-linking added alongside migration 0041: a
Designation's linked_role_id and grants_trainer_access should carry
through EmployeeService.invite_employee into a real RBAC role grant and/or
a real Trainer record, driven purely by which designation the invited
employee holds.
"""

import pytest

from modules.authentication.repository import AuthRepository
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

# What an admin actually fills in now — see EmployeeCreateRequest's own
# docstring for why everything personal is gone from this list.
_MINIMAL_EMPLOYEE_PAYLOAD = {
    "full_name": "Priya Nair",
    "email": "priya.nair@example.com",
    "date_of_joining": "2026-02-01",
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


async def test_updating_designation_to_grant_trainer_access_retroactively_grants_already_invited_employees(
    client, auth_headers, db_session, rbac_seeded
):
    """The gap this closes: a designation's grants used to only ever get
    applied at the moment an employee was invited. An employee invited
    while their designation had no trainer access — then the designation
    is edited afterward to add it — used to be stuck permanently with no
    Trainer record and no error explaining why trainer-portal access
    didn't work, even though their designation now says they should have
    it."""
    authz_repo = AuthorizationRepository(db_session)
    staff_role = await authz_repo.get_role_by_slug("staff")
    assert staff_role is not None

    department, designation = await _create_department_and_designation(client, auth_headers)
    assert designation["linked_role_id"] is None
    assert designation["grants_trainer_access"] is False

    create_resp = await client.post(
        "/api/v1/employees",
        json={
            **_EMPLOYEE_PAYLOAD,
            "email": "retroactive-trainer@example.com",
            "department_id": department["id"],
            "designation_id": designation["id"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    employee = create_resp.json()

    invite_resp = await client.post(f"/api/v1/employees/{employee['id']}/invite", headers=auth_headers)
    assert invite_resp.status_code == 200, invite_resp.text
    user_id = invite_resp.json()["user_id"]

    trainer_repo = TrainerRepository(db_session)
    trainer_before = await trainer_repo.get_by_employee_id(employee["id"], department["organization_id"])
    assert trainer_before is None

    update_resp = await client.patch(
        f"/api/v1/hr/designations/{designation['id']}",
        json={"linked_role_id": str(staff_role.id), "grants_trainer_access": True},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200, update_resp.text

    trainer_after = await trainer_repo.get_by_employee_id(employee["id"], department["organization_id"])
    assert trainer_after is not None

    user_roles = await authz_repo.get_roles_for_user(user_id)
    assert any(str(r.id) == str(staff_role.id) for r in user_roles)

    # Idempotent: saving the already-updated designation again doesn't
    # error or create a duplicate Trainer row.
    resave_resp = await client.patch(
        f"/api/v1/hr/designations/{designation['id']}",
        json={"grants_trainer_access": True},
        headers=auth_headers,
    )
    assert resave_resp.status_code == 200, resave_resp.text
    trainer_after_resave = await trainer_repo.get_by_employee_id(employee["id"], department["organization_id"])
    assert trainer_after_resave.id == trainer_after.id


async def test_reassigning_an_already_invited_employees_designation_grants_trainer_access_immediately(
    client, auth_headers, db_session, rbac_seeded
):
    department, bare_designation = await _create_department_and_designation(client, auth_headers, code="ISE")

    create_resp = await client.post(
        "/api/v1/employees",
        json={
            **_EMPLOYEE_PAYLOAD,
            "email": "reassigned-designation@example.com",
            "department_id": department["id"],
            "designation_id": bare_designation["id"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    employee = create_resp.json()

    invite_resp = await client.post(f"/api/v1/employees/{employee['id']}/invite", headers=auth_headers)
    assert invite_resp.status_code == 200, invite_resp.text

    trainer_role_designation_resp = await client.post(
        "/api/v1/hr/designations",
        json={"title": "Lead Trainer", "code": "TRAINER", "grants_trainer_access": True},
        headers=auth_headers,
    )
    assert trainer_role_designation_resp.status_code == 201, trainer_role_designation_resp.text
    trainer_designation = trainer_role_designation_resp.json()

    trainer_repo = TrainerRepository(db_session)
    trainer_before = await trainer_repo.get_by_employee_id(employee["id"], department["organization_id"])
    assert trainer_before is None

    reassign_resp = await client.patch(
        f"/api/v1/employees/{employee['id']}",
        json={"designation_id": trainer_designation["id"]},
        headers=auth_headers,
    )
    assert reassign_resp.status_code == 200, reassign_resp.text

    trainer_after = await trainer_repo.get_by_employee_id(employee["id"], department["organization_id"])
    assert trainer_after is not None


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


async def test_create_employee_without_personal_fields_succeeds(client, auth_headers, rbac_seeded):
    """The admin form only ever collects name/department/designation/
    email/date_of_joining now (see EmployeeCreateRequest's docstring) —
    a create request with none of the personal fields must not 422."""
    department, designation = await _create_department_and_designation(
        client, auth_headers, code="MIN"
    )

    create_resp = await client.post(
        "/api/v1/employees",
        json={
            **_MINIMAL_EMPLOYEE_PAYLOAD,
            "department_id": department["id"],
            "designation_id": designation["id"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    employee = create_resp.json()
    assert employee["phone"] is None
    assert employee["gender"] is None
    assert employee["address_line1"] is None


async def test_update_employee_can_correct_date_of_joining(client, auth_headers, rbac_seeded):
    """date_of_joining is set once at invite time, but HR needs to be
    able to correct it afterward (a typo, backfilling a real historical
    hire date, ...) — EmployeeUpdateRequest previously omitted the field
    entirely, so PATCH silently ignored it."""
    department, designation = await _create_department_and_designation(
        client, auth_headers, code="DOJ"
    )

    create_resp = await client.post(
        "/api/v1/employees",
        json={
            **_MINIMAL_EMPLOYEE_PAYLOAD,
            "email": "doj-test@example.com",
            "department_id": department["id"],
            "designation_id": designation["id"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    employee_id = create_resp.json()["id"]
    assert create_resp.json()["date_of_joining"] == "2026-02-01"

    update_resp = await client.patch(
        f"/api/v1/employees/{employee_id}",
        json={"date_of_joining": "2025-09-01"},
        headers=auth_headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["date_of_joining"] == "2025-09-01"


async def test_complete_registration_sets_password_and_profile(
    client, auth_headers, db_session, rbac_seeded
):
    """The employee's own side of the flow: invite_employee hands out a
    token via email (unreachable from a test — reading it straight from
    the same PasswordResetToken row the app itself would look up mirrors
    what clicking the emailed link does), and complete-registration
    should both set the password AND save the fields nobody but the
    employee ever filled in."""
    department, designation = await _create_department_and_designation(
        client, auth_headers, code="CREG"
    )
    create_resp = await client.post(
        "/api/v1/employees",
        json={
            **_MINIMAL_EMPLOYEE_PAYLOAD,
            "email": "complete-me@example.com",
            "department_id": department["id"],
            "designation_id": designation["id"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    employee_id = create_resp.json()["id"]

    invite_resp = await client.post(f"/api/v1/employees/{employee_id}/invite", headers=auth_headers)
    assert invite_resp.status_code == 200, invite_resp.text
    user_id = invite_resp.json()["user_id"]

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_id(user_id)
    reset_token = await auth_repo.create_password_reset_token(user.id)

    complete_resp = await client.post(
        "/api/v1/employees/complete-registration",
        json={
            "token": reset_token.token,
            "new_password": "NewStrongPass1!",
            "phone": "+91-9222222222",
            "gender": "female",
            "date_of_birth": "1998-03-20",
            "address_line1": "12 MG Road",
            "city": "Pune",
            "state": "Maharashtra",
            "country": "India",
            "postal_code": "411001",
            "emergency_contact_name": "Anita Nair",
            "emergency_contact_phone": "+91-9333333333",
        },
    )
    assert complete_resp.status_code == 200, complete_resp.text
    completed = complete_resp.json()
    assert completed["phone"] == "+91-9222222222"
    assert completed["address_line1"] == "12 MG Road"
    assert completed["emergency_contact_name"] == "Anita Nair"

    # The new password actually works, end to end.
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "complete-me@example.com", "password": "NewStrongPass1!"},
    )
    assert login_resp.status_code == 200, login_resp.text

    # The token is single-use, same as ordinary reset-password.
    replay_resp = await client.post(
        "/api/v1/employees/complete-registration",
        json={
            "token": reset_token.token,
            "new_password": "AnotherPass2!",
            "phone": "+91-9222222222",
            "gender": "female",
            "date_of_birth": "1998-03-20",
            "address_line1": "12 MG Road",
            "city": "Pune",
            "state": "Maharashtra",
            "country": "India",
            "postal_code": "411001",
            "emergency_contact_name": "Anita Nair",
            "emergency_contact_phone": "+91-9333333333",
        },
    )
    assert replay_resp.status_code == 422, replay_resp.text


async def test_complete_registration_rejects_invalid_token(client):
    resp = await client.post(
        "/api/v1/employees/complete-registration",
        json={
            "token": "not-a-real-token",
            "new_password": "NewStrongPass1!",
            "phone": "+91-9222222222",
            "gender": "female",
            "date_of_birth": "1998-03-20",
            "address_line1": "12 MG Road",
            "city": "Pune",
            "state": "Maharashtra",
            "country": "India",
            "postal_code": "411001",
            "emergency_contact_name": "Anita Nair",
            "emergency_contact_phone": "+91-9333333333",
        },
    )
    assert resp.status_code == 422, resp.text
