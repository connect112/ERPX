"""
API tests for modules/authorization/routes.py's per-organization role
scoping — fixed alongside the same RBAC audit as
test_organizations_access_control.py. Custom roles an organization's own
admin creates are now owned by that organization (Role.organization_id)
and must never be visible, editable, assignable, or deletable by another
organization's admin — only the platform's system role templates
(organization_id IS NULL) are shared read-only across every tenant.
"""

import uuid

import pytest

from modules.authentication.repository import AuthRepository
from modules.authorization.repository import AuthorizationRepository
from modules.organizations.repository import OrganizationRepository
from modules.users.repository import UserProfileRepository

pytestmark = pytest.mark.api


async def _create_administrator_with_login(client, db_session, organization):
    unique = uuid.uuid4().hex[:8]
    email = f"role-admin.{unique}@erpx.example.com"
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
    return user, {"Authorization": f"Bearer {login_response.json()['access_token']}"}


@pytest.fixture
async def other_organization(db_session):
    repo = OrganizationRepository(db_session)
    unique = uuid.uuid4().hex[:8]
    return await repo.create(name=f"Other Org {unique}", slug=f"other-org-{unique}")


async def test_admin_can_create_and_see_own_custom_role(client, db_session, organization, rbac_seeded):
    _admin, headers = await _create_administrator_with_login(client, db_session, organization)

    create_response = await client.post(
        "/api/v1/authorization/roles",
        json={"name": "Accountant", "slug": f"accountant_{uuid.uuid4().hex[:8]}", "description": "Org-specific"},
        headers=headers,
    )
    assert create_response.status_code == 201
    role = create_response.json()
    assert role["organization_id"] == str(organization.id)

    list_response = await client.get("/api/v1/authorization/roles", headers=headers)
    assert list_response.status_code == 200
    slugs = [r["slug"] for r in list_response.json()]
    assert role["slug"] in slugs
    # System role templates are still visible alongside the org's own.
    assert "administrator" in slugs


async def test_custom_role_invisible_to_another_organization(
    client, db_session, organization, other_organization, rbac_seeded
):
    _admin_a, headers_a = await _create_administrator_with_login(client, db_session, organization)
    _admin_b, headers_b = await _create_administrator_with_login(client, db_session, other_organization)

    create_response = await client.post(
        "/api/v1/authorization/roles",
        json={"name": "Org A Only", "slug": f"org_a_only_{uuid.uuid4().hex[:8]}", "description": None},
        headers=headers_a,
    )
    assert create_response.status_code == 201
    role_id = create_response.json()["id"]

    # Not in org B's list.
    list_response = await client.get("/api/v1/authorization/roles", headers=headers_b)
    assert role_id not in [r["id"] for r in list_response.json()]

    # 404, not 403, on every direct-access route — don't confirm it exists.
    get_response = await client.get(f"/api/v1/authorization/roles/{role_id}", headers=headers_b)
    assert get_response.status_code == 404

    update_response = await client.patch(
        f"/api/v1/authorization/roles/{role_id}", json={"name": "Hijacked"}, headers=headers_b
    )
    assert update_response.status_code == 404

    delete_response = await client.delete(f"/api/v1/authorization/roles/{role_id}", headers=headers_b)
    assert delete_response.status_code == 404

    perms_response = await client.put(
        f"/api/v1/authorization/roles/{role_id}/permissions",
        json={"permission_codes": ["dashboard.view"]},
        headers=headers_b,
    )
    assert perms_response.status_code == 404

    # Org A itself can still reach it fine.
    own_get_response = await client.get(f"/api/v1/authorization/roles/{role_id}", headers=headers_a)
    assert own_get_response.status_code == 200


async def test_same_slug_allowed_in_different_organizations(
    client, db_session, organization, other_organization, rbac_seeded
):
    _admin_a, headers_a = await _create_administrator_with_login(client, db_session, organization)
    _admin_b, headers_b = await _create_administrator_with_login(client, db_session, other_organization)
    shared_slug = f"trainer_lead_{uuid.uuid4().hex[:8]}"

    response_a = await client.post(
        "/api/v1/authorization/roles",
        json={"name": "Trainer Lead", "slug": shared_slug, "description": None},
        headers=headers_a,
    )
    assert response_a.status_code == 201

    response_b = await client.post(
        "/api/v1/authorization/roles",
        json={"name": "Trainer Lead", "slug": shared_slug, "description": None},
        headers=headers_b,
    )
    assert response_b.status_code == 201
    assert response_a.json()["id"] != response_b.json()["id"]


async def test_cannot_assign_another_organizations_role_to_own_user(
    client, db_session, organization, other_organization, rbac_seeded
):
    _admin_a, headers_a = await _create_administrator_with_login(client, db_session, organization)
    admin_b, headers_b = await _create_administrator_with_login(client, db_session, other_organization)

    create_response = await client.post(
        "/api/v1/authorization/roles",
        json={"name": "Org A Only", "slug": f"org_a_only_{uuid.uuid4().hex[:8]}", "description": None},
        headers=headers_a,
    )
    role_id = create_response.json()["id"]

    # Org B admin tries to assign Org A's custom role to themselves.
    assign_response = await client.post(
        "/api/v1/authorization/user-roles",
        json={"user_id": str(admin_b.id), "role_id": role_id},
        headers=headers_b,
    )
    assert assign_response.status_code == 404


async def test_cannot_assign_role_to_user_in_another_organization(
    client, db_session, organization, other_organization, rbac_seeded
):
    _admin_a, headers_a = await _create_administrator_with_login(client, db_session, organization)
    _admin_b, _headers_b = await _create_administrator_with_login(client, db_session, other_organization)

    authz_repo = AuthorizationRepository(db_session)
    staff_role = await authz_repo.get_role_by_slug("staff")

    # Org A admin tries to grant a role to Org B's admin — cross-tenant,
    # must fail even though both role and target user "exist".
    assign_response = await client.post(
        "/api/v1/authorization/user-roles",
        json={"user_id": str(_admin_b.id), "role_id": str(staff_role.id)},
        headers=headers_a,
    )
    assert assign_response.status_code == 404
