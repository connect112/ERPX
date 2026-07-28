"""
API tests for the Workshops module: staff CRUD/management plus the
student self-service surface (browse published workshops, register,
view own registrations). Registration is open to both enrolled students
and public contacts, so most tests exercise the public-registration path
directly while the self-service tests confirm ownership isolation.
"""

import uuid
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.api


def _future_date(days: int = 14) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


async def _create_workshop(client, auth_headers, **overrides):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "code": f"WS-{unique}",
        "title": "Intro to Cloud Security",
        "workshop_date": _future_date(),
        "start_time": "10:00:00",
        "end_time": "13:00:00",
        "capacity": 2,
    }
    payload.update(overrides)
    response = await client.post("/api/v1/workshops", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_and_get_workshop(client, auth_headers):
    workshop = await _create_workshop(client, auth_headers)
    assert workshop["status"] == "draft"
    assert workshop["fee"] == 0

    get_response = await client.get(f"/api/v1/workshops/{workshop['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Intro to Cloud Security"


async def test_duplicate_workshop_code_rejected(client, auth_headers):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "code": f"DUP-{unique}",
        "title": "Duplicate Workshop",
        "workshop_date": _future_date(),
        "start_time": "10:00:00",
        "end_time": "12:00:00",
    }
    first = await client.post("/api/v1/workshops", json=payload, headers=auth_headers)
    assert first.status_code == 201
    second = await client.post("/api/v1/workshops", json=payload, headers=auth_headers)
    assert second.status_code == 409


async def test_registration_rejected_before_publish(client, auth_headers):
    workshop = await _create_workshop(client, auth_headers)
    response = await client.post(
        f"/api/v1/workshops/{workshop['id']}/registrations",
        json={"contact_name": "Walk-in Attendee", "contact_email": "walkin@example.com"},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_public_registration_respects_capacity(client, auth_headers):
    workshop = await _create_workshop(client, auth_headers, capacity=1)
    publish = await client.post(
        f"/api/v1/workshops/{workshop['id']}/status", json={"status": "published"}, headers=auth_headers
    )
    assert publish.status_code == 200

    first = await client.post(
        f"/api/v1/workshops/{workshop['id']}/registrations",
        json={"contact_name": "First Attendee", "contact_email": "first@example.com"},
        headers=auth_headers,
    )
    assert first.status_code == 201
    assert first.json()["is_paid"] is True  # free workshop (fee=0)

    second = await client.post(
        f"/api/v1/workshops/{workshop['id']}/registrations",
        json={"contact_name": "Second Attendee", "contact_email": "second@example.com"},
        headers=auth_headers,
    )
    assert second.status_code == 422  # capacity reached


async def test_mark_attendance_and_cancel_registration(client, auth_headers):
    workshop = await _create_workshop(client, auth_headers)
    await client.post(
        f"/api/v1/workshops/{workshop['id']}/status", json={"status": "published"}, headers=auth_headers
    )
    registration_response = await client.post(
        f"/api/v1/workshops/{workshop['id']}/registrations",
        json={"contact_name": "Attendee", "contact_email": "attendee@example.com"},
        headers=auth_headers,
    )
    registration_id = registration_response.json()["id"]

    attend_response = await client.post(
        f"/api/v1/workshops/registrations/{registration_id}/attendance",
        json={"attended": True},
        headers=auth_headers,
    )
    assert attend_response.status_code == 200
    assert attend_response.json()["status"] == "attended"

    cancel_response = await client.post(
        f"/api/v1/workshops/registrations/{registration_id}/cancel", headers=auth_headers
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


async def test_staff_without_permission_cannot_manage_workshops(client, staff_headers):
    response = await client.post(
        "/api/v1/workshops",
        json={
            "code": "NOAUTH-01",
            "title": "Unauthorized Workshop",
            "workshop_date": _future_date(),
            "start_time": "10:00:00",
            "end_time": "12:00:00",
        },
        headers=staff_headers,
    )
    assert response.status_code == 403


async def test_student_can_browse_and_register_for_published_workshop(
    client, db_session, organization, auth_headers
):
    from datetime import date as date_cls

    from modules.authentication.repository import AuthRepository
    from modules.students.repository import StudentRepository
    from modules.users.repository import UserProfileRepository

    workshop = await _create_workshop(client, auth_headers)
    await client.post(
        f"/api/v1/workshops/{workshop['id']}/status", json={"status": "published"}, headers=auth_headers
    )

    unique = uuid.uuid4().hex[:8]
    email = f"ws.student.{unique}@erpx.example.com"
    password = "StudentPass1!"
    register_response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Workshop Student"}
    )
    assert register_response.status_code == 201

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)
    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)
    student = await StudentRepository(db_session).create(
        organization.id,
        user_id=user.id,
        full_name="Workshop Student",
        course_name="Python Bootcamp",
        enrollment_date=date_cls(2026, 1, 1),
    )
    await db_session.flush()

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    list_response = await client.get("/api/v1/workshops/me", headers=headers)
    assert list_response.status_code == 200
    assert any(w["id"] == workshop["id"] for w in list_response.json())

    register_self_response = await client.post(
        f"/api/v1/workshops/{workshop['id']}/register/me", headers=headers
    )
    assert register_self_response.status_code == 201, register_self_response.text
    assert register_self_response.json()["student_id"] == student.id.__str__()

    duplicate_response = await client.post(
        f"/api/v1/workshops/{workshop['id']}/register/me", headers=headers
    )
    assert duplicate_response.status_code == 409

    my_registrations_response = await client.get("/api/v1/workshops/me/registrations", headers=headers)
    assert my_registrations_response.status_code == 200
    assert len(my_registrations_response.json()) == 1
