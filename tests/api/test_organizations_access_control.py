"""
API tests for modules/organizations/routes.py's access control — fixed
alongside the RBAC audit that found a genuine cross-tenant bug:
organizations.view/organizations.manage were part of the default
Administrator permission grant, and the routes had no org-scoping at all,
so any customer's own tenant Administrator could list/view/edit/delete
*any other* customer's organization record. Now: creating, listing every
tenant, and editing/deleting a tenant require true platform access
(User.is_superuser via require_superuser()) — a permission code alone,
however named, is no longer enough. The one exception is viewing your
own organization's record, which any authenticated user can do
(ownership-is-authorization, same as every other "me" endpoint).
"""

import uuid

import pytest

from modules.authorization.repository import AuthorizationRepository
from modules.organizations.repository import OrganizationRepository

pytestmark = pytest.mark.api


async def _create_administrator_with_login(client, db_session, organization, rbac_seeded):
    """A real (non-superuser) tenant admin — holds the "administrator"
    system role, same as a real customer's own admin account would."""
    from modules.authentication.repository import AuthRepository
    from modules.users.repository import UserProfileRepository

    unique = uuid.uuid4().hex[:8]
    email = f"tenant-admin.{unique}@erpx.example.com"
    password = "TenantAdmin1!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Tenant Admin"},
    )
    assert register_response.status_code == 201

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)
    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    authz_repo = AuthorizationRepository(db_session)
    admin_role = await authz_repo.get_role_by_slug("administrator")
    await authz_repo.assign_role(user.id, admin_role.id, assigned_by_user_id=None)
    await db_session.flush()

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


@pytest.fixture
async def other_organization(db_session):
    repo = OrganizationRepository(db_session)
    unique = uuid.uuid4().hex[:8]
    return await repo.create(name=f"Other Org {unique}", slug=f"other-org-{unique}")


async def test_tenant_administrator_can_view_own_organization(
    client, db_session, organization, rbac_seeded
):
    headers = await _create_administrator_with_login(client, db_session, organization, rbac_seeded)

    resp = await client.get(f"/api/v1/organizations/{organization.id}", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == str(organization.id)


async def test_tenant_administrator_cannot_view_another_organization(
    client, db_session, organization, other_organization, rbac_seeded
):
    headers = await _create_administrator_with_login(client, db_session, organization, rbac_seeded)

    resp = await client.get(f"/api/v1/organizations/{other_organization.id}", headers=headers)
    assert resp.status_code == 403, resp.text


async def test_tenant_administrator_cannot_list_organizations(
    client, db_session, organization, rbac_seeded
):
    headers = await _create_administrator_with_login(client, db_session, organization, rbac_seeded)

    resp = await client.get("/api/v1/organizations", headers=headers)
    assert resp.status_code == 403, resp.text


async def test_tenant_administrator_cannot_create_organization(
    client, db_session, organization, rbac_seeded
):
    headers = await _create_administrator_with_login(client, db_session, organization, rbac_seeded)

    resp = await client.post(
        "/api/v1/organizations", json={"name": "Sneaky Org", "slug": f"sneaky-{uuid.uuid4().hex[:8]}"}, headers=headers
    )
    assert resp.status_code == 403, resp.text


async def test_tenant_administrator_cannot_delete_another_organization(
    client, db_session, organization, other_organization, rbac_seeded
):
    headers = await _create_administrator_with_login(client, db_session, organization, rbac_seeded)

    resp = await client.delete(f"/api/v1/organizations/{other_organization.id}", headers=headers)
    assert resp.status_code == 403, resp.text


async def test_staff_with_no_role_can_still_view_own_organization(client, staff_headers, organization):
    """Ownership, not a granted permission, is what authorizes this one —
    even a zero-permission account can see their own org's basic record."""
    resp = await client.get(f"/api/v1/organizations/{organization.id}", headers=staff_headers)
    assert resp.status_code == 200, resp.text


async def test_superuser_can_list_and_view_any_organization(
    client, auth_headers, organization, other_organization
):
    list_resp = await client.get("/api/v1/organizations", headers=auth_headers)
    assert list_resp.status_code == 200, list_resp.text

    get_resp = await client.get(f"/api/v1/organizations/{other_organization.id}", headers=auth_headers)
    assert get_resp.status_code == 200, get_resp.text
