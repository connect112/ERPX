"""
API tests asserting role-based access control actually gates endpoints —
not just that endpoints exist and return data for a superuser.
"""

import pytest

from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService

pytestmark = [pytest.mark.api, pytest.mark.security]


async def test_protected_endpoint_rejects_unauthenticated_request(client):
    response = await client.get("/api/v1/employees")
    assert response.status_code == 401


async def test_staff_without_any_role_is_forbidden(client, staff_headers):
    response = await client.get("/api/v1/employees", headers=staff_headers)
    assert response.status_code == 403


async def test_superuser_bypasses_permission_checks(client, auth_headers):
    response = await client.get("/api/v1/employees", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert body["items"] == []


async def test_assigning_staff_role_grants_view_access(client, staff_headers, staff_user, db_session, rbac_seeded):
    user, _ = staff_user
    authz_repo = AuthorizationRepository(db_session)
    authz_service = AuthorizationService(db_session)

    staff_role = await authz_repo.get_role_by_slug("staff")
    assert staff_role is not None, "seed_default_rbac should have created the system 'staff' role"

    await authz_service.assign_role(user.id, staff_role.id, assigned_by_user_id=None)

    response = await client.get("/api/v1/employees", headers=staff_headers)
    assert response.status_code == 200


async def test_staff_role_does_not_grant_manage_permission(client, staff_headers, staff_user, db_session, rbac_seeded):
    """Staff gets employees.view from the default role, but not employees.manage — creating one should still be forbidden."""
    user, _ = staff_user
    authz_repo = AuthorizationRepository(db_session)
    authz_service = AuthorizationService(db_session)

    staff_role = await authz_repo.get_role_by_slug("staff")
    await authz_service.assign_role(user.id, staff_role.id, assigned_by_user_id=None)

    response = await client.post(
        "/api/v1/employees",
        headers=staff_headers,
        json={
            "employee_code": "EMP-001",
            "full_name": "Should Not Be Created",
            "employment_type": "full_time",
            "date_of_joining": "2026-01-01",
        },
    )
    assert response.status_code == 403
