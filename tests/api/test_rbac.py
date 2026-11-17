"""
API tests asserting role-based access control actually gates endpoints —
not just that endpoints exist and return data for a superuser.
"""

import uuid

import pytest

from app.core.security import create_access_token, hash_password
from modules.authentication.models import UserStatus
from modules.authentication.repository import AuthRepository
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


async def test_assigning_staff_role_grants_view_access(
    client, staff_headers, staff_user, organization, db_session, rbac_seeded
):
    user, _ = staff_user
    authz_repo = AuthorizationRepository(db_session)
    authz_service = AuthorizationService(db_session)

    staff_role = await authz_repo.get_role_by_slug("staff")
    assert staff_role is not None, "seed_default_rbac should have created the system 'staff' role"

    await authz_service.assign_role(user.id, staff_role.id, organization.id, assigned_by_user_id=None)

    response = await client.get("/api/v1/employees", headers=staff_headers)
    assert response.status_code == 200


async def test_get_my_roles_requires_no_permission_and_reflects_actual_grants(
    client, staff_headers, staff_user, organization, db_session, rbac_seeded
):
    """GET /authorization/me is deliberately unlike GET /users/{id}/roles —
    reading your OWN roles/permissions needs no authorization.roles.view/
    users.view grant at all (ownership is the authorization), unlike
    looking up someone else's."""
    user, _ = staff_user
    authz_repo = AuthorizationRepository(db_session)
    authz_service = AuthorizationService(db_session)

    # A role-less user still gets 200 (not 403) — just an empty grant set.
    empty_response = await client.get("/api/v1/authorization/me", headers=staff_headers)
    assert empty_response.status_code == 200
    assert empty_response.json()["roles"] == []
    assert empty_response.json()["effective_permissions"] == []
    assert empty_response.json()["is_superuser"] is False
    # the caller's organization comes back too (clients keep per-user, per-organization browser preferences apart with it)
    assert empty_response.json()["organization_id"] == str(organization.id)

    staff_role = await authz_repo.get_role_by_slug("staff")
    await authz_service.assign_role(user.id, staff_role.id, organization.id, assigned_by_user_id=None)

    response = await client.get("/api/v1/authorization/me", headers=staff_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user.id)
    assert any(r["slug"] == "staff" for r in body["roles"])
    assert "employees.view" in body["effective_permissions"]
    assert "employees.manage" not in body["effective_permissions"]


async def test_get_my_roles_requires_authentication(client):
    response = await client.get("/api/v1/authorization/me")
    assert response.status_code == 401


async def test_get_my_roles_reports_is_superuser(client, auth_headers, rbac_seeded):
    """auth_headers is a superuser with no roles assigned (see
    tests/_fixtures.py) -- is_superuser must still come back true even
    with an empty roles/effective_permissions list, since it's a
    separate bypass flag, not derived from role assignments."""
    response = await client.get("/api/v1/authorization/me", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["is_superuser"] is True
    assert body["roles"] == []


async def test_staff_role_does_not_grant_manage_permission(
    client, staff_headers, staff_user, organization, db_session, rbac_seeded
):
    """Staff gets employees.view from the default role, but not employees.manage — creating one should still be forbidden."""
    user, _ = staff_user
    authz_repo = AuthorizationRepository(db_session)
    authz_service = AuthorizationService(db_session)

    staff_role = await authz_repo.get_role_by_slug("staff")
    await authz_service.assign_role(user.id, staff_role.id, organization.id, assigned_by_user_id=None)

    response = await client.post(
        "/api/v1/employees",
        headers=staff_headers,
        json={
            "full_name": "Should Not Be Created",
            "employment_type": "full_time",
            "date_of_joining": "2026-01-01",
        },
    )
    assert response.status_code == 403


async def test_get_my_roles_returns_the_organization_of_a_normal_administrator(
    client, staff_headers, staff_user, organization, db_session, rbac_seeded
):
    """organization_id is what the web app scopes per-user browser preferences (the navigation Favorites) by."""
    user, _ = staff_user
    role = await AuthorizationRepository(db_session).get_role_by_slug("administrator")
    await AuthorizationService(db_session).assign_role(user.id, role.id, organization.id, assigned_by_user_id=None)
    response = await client.get("/api/v1/authorization/me", headers=staff_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == str(organization.id)
    assert body["is_superuser"] is False
    assert any(r["slug"] == "administrator" for r in body["roles"])
    assert len(body["effective_permissions"]) > 100  # the rest of the response is exactly what it was


async def test_get_my_roles_for_a_platform_superuser_without_a_profile(client, db_session, rbac_seeded):
    """A platform superuser may have no organization profile at all: the request still succeeds, with organization_id null."""
    user = await AuthRepository(db_session).create_user(
        email=f"platform-{uuid.uuid4().hex[:8]}@erpx.example.com", hashed_password=hash_password("Test1234!"), full_name="Platform Admin"
    )
    user.status = UserStatus.ACTIVE
    user.is_email_verified = True
    user.is_superuser = True
    await db_session.flush()
    response = await client.get("/api/v1/authorization/me", headers={"Authorization": f"Bearer {create_access_token(str(user.id))}"})
    assert response.status_code == 200
    body = response.json()
    assert body["is_superuser"] is True
    assert body["organization_id"] is None
    assert body["roles"] == []
    assert body["user_id"] == str(user.id)
