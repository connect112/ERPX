"""
API tests for the Events module: an org-wide calendar for ad-hoc entries
(holidays, meetings, announcements) that don't belong to any single
business module. Staff manage events; any authenticated org member can
view the calendar (no permission required to read — matching how a
company calendar works).
"""

import uuid
from datetime import date, timedelta

import pytest

from app.core.security import create_access_token, hash_password
from modules.authentication.models import User, UserStatus
from modules.authentication.repository import AuthRepository
from modules.users.repository import UserProfileRepository

pytestmark = pytest.mark.api


async def _make_plain_user(client, db_session, organization):
    unique = uuid.uuid4().hex[:8]
    auth_repo = AuthRepository(db_session)
    user = await auth_repo.create_user(
        email=f"events.{unique}@erpx.example.com",
        hashed_password=hash_password("Test1234!"),
        full_name="Plain User",
    )
    user.status = UserStatus.ACTIVE
    user.is_email_verified = True
    await db_session.flush()
    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)
    await db_session.flush()
    token = create_access_token(str(user.id))
    return user, {"Authorization": f"Bearer {token}"}


def _iso(days_from_now: int) -> str:
    return (date.today() + timedelta(days=days_from_now)).isoformat() + "T09:00:00Z"


async def test_create_and_list_event(client, auth_headers):
    response = await client.post(
        "/api/v1/events",
        json={
            "title": "Independence Day",
            "event_type": "holiday",
            "start_at": _iso(10),
            "is_all_day": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    event = response.json()
    assert event["event_type"] == "holiday"
    assert event["is_all_day"] is True

    list_response = await client.get("/api/v1/events", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(e["id"] == event["id"] for e in list_response.json()["items"])


async def test_any_authenticated_user_can_view_calendar(client, db_session, organization, auth_headers):
    await client.post(
        "/api/v1/events",
        json={"title": "All-hands", "event_type": "meeting", "start_at": _iso(3)},
        headers=auth_headers,
    )
    _user, headers = await _make_plain_user(client, db_session, organization)

    list_response = await client.get("/api/v1/events", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1


async def test_plain_user_cannot_create_event(client, db_session, organization):
    _user, headers = await _make_plain_user(client, db_session, organization)
    response = await client.post(
        "/api/v1/events",
        json={"title": "Unauthorized meeting", "start_at": _iso(1)},
        headers=headers,
    )
    assert response.status_code == 403


async def test_filter_by_event_type(client, auth_headers):
    await client.post(
        "/api/v1/events",
        json={"title": "Holiday A", "event_type": "holiday", "start_at": _iso(5)},
        headers=auth_headers,
    )
    await client.post(
        "/api/v1/events",
        json={"title": "Meeting B", "event_type": "meeting", "start_at": _iso(6)},
        headers=auth_headers,
    )

    response = await client.get("/api/v1/events", params={"event_type": "holiday"}, headers=auth_headers)
    assert response.status_code == 200
    assert all(e["event_type"] == "holiday" for e in response.json()["items"])


async def test_update_and_delete_event(client, auth_headers):
    create_response = await client.post(
        "/api/v1/events",
        json={"title": "Draft Event", "start_at": _iso(2)},
        headers=auth_headers,
    )
    event_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/events/{event_id}", json={"title": "Updated Event", "location": "Auditorium"}, headers=auth_headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated Event"
    assert update_response.json()["location"] == "Auditorium"

    delete_response = await client.delete(f"/api/v1/events/{event_id}", headers=auth_headers)
    assert delete_response.status_code == 200

    get_response = await client.get(f"/api/v1/events/{event_id}", headers=auth_headers)
    assert get_response.status_code == 404
