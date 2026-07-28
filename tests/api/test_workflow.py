"""
API tests for the Workflow module: a generic, entity-agnostic approval
engine. Other modules would call `ApprovalRequestService` directly
in-process; these tests exercise the same engine through its HTTP
surface with a synthetic `entity_type` ("test_entity") since no other
module has been wired to it yet. Coverage: multi-step approval chains
advance correctly, a rejection at any step terminates the whole
request, only the current step's role can act, and only the original
requester can cancel.
"""

import uuid

import pytest

from app.core.security import create_access_token, hash_password
from modules.authentication.models import User, UserStatus
from modules.authentication.repository import AuthRepository
from modules.authorization.repository import AuthorizationRepository
from modules.users.repository import UserProfileRepository

pytestmark = pytest.mark.api


async def _make_role_user(client, db_session, organization, role_name: str):
    """Creates a user holding a freshly-created role named `role_name`, returning (role, headers)."""
    unique = uuid.uuid4().hex[:8]
    authz_repo = AuthorizationRepository(db_session)
    role = await authz_repo.create_role(f"{role_name} {unique}", f"{role_name.lower()}-{unique}", None)

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.create_user(
        email=f"{role_name.lower()}.{unique}@erpx.example.com",
        hashed_password=hash_password("Test1234!"),
        full_name=f"{role_name} User",
    )
    user.status = UserStatus.ACTIVE
    user.is_email_verified = True
    await db_session.flush()

    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)
    await authz_repo.assign_role(user.id, role.id, assigned_by_user_id=None)
    await db_session.flush()

    token = create_access_token(str(user.id))
    return role, user, {"Authorization": f"Bearer {token}"}


async def _create_two_step_workflow(client, auth_headers, manager_role_id, director_role_id, entity_type):
    response = await client.post(
        "/api/v1/workflow/workflows",
        json={
            "entity_type": entity_type,
            "name": "Standard approval",
            "steps": [
                {"step_order": 1, "approver_role_id": str(manager_role_id), "name": "Manager review"},
                {"step_order": 2, "approver_role_id": str(director_role_id), "name": "Director sign-off"},
            ],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_workflow_with_steps(client, auth_headers, db_session, organization):
    manager_role, _, _ = await _make_role_user(client, db_session, organization, "Manager")
    director_role, _, _ = await _make_role_user(client, db_session, organization, "Director")

    workflow = await _create_two_step_workflow(
        client, auth_headers, manager_role.id, director_role.id, "test_entity_create"
    )
    assert workflow["entity_type"] == "test_entity_create"
    assert len(workflow["steps"]) == 2
    assert workflow["steps"][0]["step_order"] == 1


async def test_staff_without_permission_cannot_manage_workflows(client, staff_headers):
    response = await client.post(
        "/api/v1/workflow/workflows",
        json={"entity_type": "x", "name": "x", "steps": [{"step_order": 1, "approver_role_id": str(uuid.uuid4())}]},
        headers=staff_headers,
    )
    assert response.status_code == 403


async def test_submit_without_configured_workflow_is_rejected(client, auth_headers):
    response = await client.post(
        "/api/v1/workflow/requests",
        json={"entity_type": "no_such_entity_type", "entity_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_two_step_approval_chain_and_wrong_step_rejection(client, auth_headers, db_session, organization):
    entity_type = "test_entity_chain"
    manager_role, _manager_user, manager_headers = await _make_role_user(
        client, db_session, organization, "Manager"
    )
    director_role, _director_user, director_headers = await _make_role_user(
        client, db_session, organization, "Director"
    )
    await _create_two_step_workflow(client, auth_headers, manager_role.id, director_role.id, entity_type)

    entity_id = str(uuid.uuid4())
    submit_response = await client.post(
        "/api/v1/workflow/requests",
        json={"entity_type": entity_type, "entity_id": entity_id},
        headers=auth_headers,
    )
    assert submit_response.status_code == 201, submit_response.text
    request = submit_response.json()
    assert request["current_step_order"] == 1
    assert request["status"] == "pending"

    # A duplicate submission while one is already pending is rejected.
    duplicate_response = await client.post(
        "/api/v1/workflow/requests",
        json={"entity_type": entity_type, "entity_id": entity_id},
        headers=auth_headers,
    )
    assert duplicate_response.status_code == 409

    # The director (step 2) cannot act while the request is still at step 1.
    wrong_step_response = await client.post(
        f"/api/v1/workflow/requests/{request['id']}/approve", json={}, headers=director_headers
    )
    assert wrong_step_response.status_code == 403

    # The manager's pending-approvals list should include this request.
    manager_pending_response = await client.get(
        "/api/v1/workflow/requests/me/pending-approvals", headers=manager_headers
    )
    assert manager_pending_response.status_code == 200
    assert any(r["id"] == request["id"] for r in manager_pending_response.json())

    manager_approve_response = await client.post(
        f"/api/v1/workflow/requests/{request['id']}/approve",
        json={"comment": "Looks good to me."},
        headers=manager_headers,
    )
    assert manager_approve_response.status_code == 200
    advanced = manager_approve_response.json()
    assert advanced["current_step_order"] == 2
    assert advanced["status"] == "pending"

    # The manager cannot approve again now that the request has moved on.
    manager_again_response = await client.post(
        f"/api/v1/workflow/requests/{request['id']}/approve", json={}, headers=manager_headers
    )
    assert manager_again_response.status_code == 403

    director_approve_response = await client.post(
        f"/api/v1/workflow/requests/{request['id']}/approve",
        json={"comment": "Approved."},
        headers=director_headers,
    )
    assert director_approve_response.status_code == 200
    final = director_approve_response.json()
    assert final["status"] == "approved"
    assert final["resolved_at"] is not None

    actions_response = await client.get(
        f"/api/v1/workflow/requests/{request['id']}/actions", headers=auth_headers
    )
    assert actions_response.status_code == 200
    actions = actions_response.json()
    assert len(actions) == 2
    assert [a["decision"] for a in actions] == ["approved", "approved"]


async def test_rejection_terminates_request(client, auth_headers, db_session, organization):
    entity_type = "test_entity_reject"
    manager_role, _, manager_headers = await _make_role_user(client, db_session, organization, "Manager")
    director_role, _, _ = await _make_role_user(client, db_session, organization, "Director")
    await _create_two_step_workflow(client, auth_headers, manager_role.id, director_role.id, entity_type)

    submit_response = await client.post(
        "/api/v1/workflow/requests",
        json={"entity_type": entity_type, "entity_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    request = submit_response.json()

    reject_response = await client.post(
        f"/api/v1/workflow/requests/{request['id']}/reject",
        json={"comment": "Not approved."},
        headers=manager_headers,
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"

    # A resolved request cannot be acted on again.
    second_action_response = await client.post(
        f"/api/v1/workflow/requests/{request['id']}/approve", json={}, headers=manager_headers
    )
    assert second_action_response.status_code == 422


async def test_only_requester_can_cancel(client, auth_headers, db_session, organization):
    entity_type = "test_entity_cancel"
    manager_role, _, _ = await _make_role_user(client, db_session, organization, "Manager")
    director_role, _, _ = await _make_role_user(client, db_session, organization, "Director")
    await _create_two_step_workflow(client, auth_headers, manager_role.id, director_role.id, entity_type)

    submit_response = await client.post(
        "/api/v1/workflow/requests",
        json={"entity_type": entity_type, "entity_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    request = submit_response.json()

    _, _, other_headers = await _make_role_user(client, db_session, organization, "Bystander")
    forbidden_response = await client.post(
        f"/api/v1/workflow/requests/{request['id']}/cancel", headers=other_headers
    )
    assert forbidden_response.status_code == 403

    cancel_response = await client.post(
        f"/api/v1/workflow/requests/{request['id']}/cancel", headers=auth_headers
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
