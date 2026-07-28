"""
API tests for corporate client self-service ("me") endpoints — the
foundation the corporate portal depends on. `Client.user_id` is the
client-portal login, resolved via `get_current_client`. These verify a
logged-in client contact sees only their own organization's tickets,
projects, and contracts (ownership, not RBAC permission), can raise a
new ticket and reply to it, and critically can't see another client's
data or another client's internal-only ticket comments.
"""

import uuid
from datetime import date

import pytest

from modules.corporate.clients.repository import ClientRepository
from modules.corporate.contracts.models import ContractType
from modules.corporate.contracts.repository import ContractRepository
from modules.corporate.projects.models import ProjectType
from modules.corporate.projects.repository import ProjectRepository
from modules.corporate.tickets.repository import SupportTicketRepository, TicketCommentRepository

pytestmark = pytest.mark.api


@pytest.fixture
def register_payload():
    return {
        "email": "no.client.link@erpx.example.com",
        "password": "StrongPass1!",
        "full_name": "No Client Link",
    }


async def _create_client_with_login(client, db_session, organization, full_name="Test Client Contact"):
    """Registers a real user, verifies them, then links a Client record to that user."""
    unique = uuid.uuid4().hex[:8]
    email = f"client.{unique}@erpx.example.com"
    password = "ClientPass1!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register_response.status_code == 201
    user_id = register_response.json()["id"]

    from modules.authentication.repository import AuthRepository

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)

    from modules.users.repository import UserProfileRepository

    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    corp_client = await ClientRepository(db_session).create(
        organization_id=organization.id,
        user_id=user.id,
        client_code=f"CLI-{unique}",
        name=f"{full_name} Corp",
        contact_person_name=full_name,
    )
    await db_session.flush()

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return corp_client, {"Authorization": f"Bearer {token}"}


async def test_client_can_view_own_profile(client, db_session, organization):
    corp_client, headers = await _create_client_with_login(client, db_session, organization)

    response = await client.get("/api/v1/corporate/clients/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(corp_client.id)
    assert response.json()["name"] == "Test Client Contact Corp"


async def test_user_without_linked_client_gets_clear_error(client, register_payload, db_session):
    from modules.authentication.repository import AuthRepository

    await client.post("/api/v1/auth/register", json=register_payload)
    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(register_payload["email"])
    await auth_repo.mark_email_verified(user)

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = await client.get("/api/v1/corporate/clients/me", headers=headers)
    assert response.status_code == 422


async def test_client_can_raise_and_reply_to_own_ticket(client, db_session, organization):
    corp_client, headers = await _create_client_with_login(client, db_session, organization)

    create_response = await client.post(
        "/api/v1/corporate/tickets/me",
        json={"subject": "VPN not working", "description": "Cannot connect since this morning."},
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    ticket = create_response.json()
    assert ticket["client_id"] == str(corp_client.id)
    assert ticket["status"] == "open"

    list_response = await client.get("/api/v1/corporate/tickets/me", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == ticket["id"]

    comment_response = await client.post(
        f"/api/v1/corporate/tickets/me/{ticket['id']}/comments",
        json={"comment_text": "Still broken after restart."},
        headers=headers,
    )
    assert comment_response.status_code == 201
    assert comment_response.json()["is_internal"] is False

    comments_response = await client.get(
        f"/api/v1/corporate/tickets/me/{ticket['id']}/comments", headers=headers
    )
    assert comments_response.status_code == 200
    assert len(comments_response.json()) == 1


async def test_client_ticket_comments_hide_internal_notes(client, db_session, organization, auth_headers):
    corp_client, headers = await _create_client_with_login(client, db_session, organization)

    ticket = await SupportTicketRepository(db_session).create(
        organization_id=organization.id,
        client_id=corp_client.id,
        ticket_number=f"TKT-INT-{uuid.uuid4().hex[:6]}",
        subject="Firewall rule request",
        description="Please open port 8443.",
    )
    await TicketCommentRepository(db_session).create(
        ticket_id=ticket.id, comment_text="Escalated to network team internally.", is_internal=True
    )
    await TicketCommentRepository(db_session).create(
        ticket_id=ticket.id, comment_text="We're looking into this.", is_internal=False
    )
    await db_session.flush()

    response = await client.get(
        f"/api/v1/corporate/tickets/me/{ticket.id}/comments", headers=headers
    )
    assert response.status_code == 200
    comments = response.json()
    assert len(comments) == 1
    assert comments[0]["comment_text"] == "We're looking into this."


async def test_client_cannot_see_another_clients_ticket(client, db_session, organization):
    _client_a, headers_a = await _create_client_with_login(
        client, db_session, organization, full_name="Client A"
    )
    client_b, _headers_b = await _create_client_with_login(
        client, db_session, organization, full_name="Client B"
    )

    ticket = await SupportTicketRepository(db_session).create(
        organization_id=organization.id,
        client_id=client_b.id,
        ticket_number=f"TKT-ISO-{uuid.uuid4().hex[:6]}",
        subject="Client B's private ticket",
        description="Should not be visible to client A.",
    )
    await db_session.flush()

    response = await client.get(f"/api/v1/corporate/tickets/me/{ticket.id}", headers=headers_a)
    assert response.status_code == 403

    list_response = await client.get("/api/v1/corporate/tickets/me", headers=headers_a)
    assert list_response.status_code == 200
    assert list_response.json() == []


async def test_client_sees_own_projects_and_contracts_only(client, db_session, organization):
    client_a, headers_a = await _create_client_with_login(
        client, db_session, organization, full_name="Project Client A"
    )
    client_b, _headers_b = await _create_client_with_login(
        client, db_session, organization, full_name="Project Client B"
    )

    await ProjectRepository(db_session).create(
        organization_id=organization.id,
        client_id=client_b.id,
        project_code=f"PRJ-{uuid.uuid4().hex[:6]}",
        name="Client B's Project",
        project_type=ProjectType.VAPT,
        start_date=date(2026, 1, 1),
    )
    contract_number = f"CTR-{uuid.uuid4().hex[:6]}"
    await ContractRepository(db_session).create(
        organization_id=organization.id,
        client_id=client_a.id,
        contract_number=contract_number,
        contract_type=ContractType.AMC,
        start_date=date(2026, 1, 1),
        contract_value=50000,
    )
    await db_session.flush()

    projects_response = await client.get("/api/v1/corporate/projects/me", headers=headers_a)
    assert projects_response.status_code == 200
    assert projects_response.json() == []

    contracts_response = await client.get("/api/v1/corporate/contracts/me", headers=headers_a)
    assert contracts_response.status_code == 200
    assert len(contracts_response.json()) == 1
    assert contracts_response.json()[0]["contract_number"] == contract_number
