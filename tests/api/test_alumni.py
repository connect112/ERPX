"""
API tests for the Alumni module: self-service profile creation, event
registration, and job referrals, plus staff moderation (profile
verification, event CRUD, attendance marking). A student needs their own
`AlumniProfile` before they can register for events or post referrals —
those dependent flows are the key edge cases alongside the happy path.
"""

import uuid
from datetime import date, timedelta

import pytest

from modules.authentication.repository import AuthRepository
from modules.students.repository import StudentRepository
from modules.users.repository import UserProfileRepository

pytestmark = pytest.mark.api


async def _create_student_with_login(client, db_session, organization, full_name="Test Student"):
    unique = uuid.uuid4().hex[:8]
    email = f"alumni.{unique}@erpx.example.com"
    password = "StudentPass1!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register_response.status_code == 201

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)
    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    student = await StudentRepository(db_session).create(
        organization.id,
        user_id=user.id,
        full_name=full_name,
        course_name="Python Bootcamp",
        enrollment_date=date(2022, 1, 1),
    )
    await db_session.flush()

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return student, {"Authorization": f"Bearer {token}"}


async def _create_event(client, auth_headers, **overrides):
    payload = {
        "title": "Annual Alumni Meetup",
        "mode": "virtual",
        "meeting_link": "https://meet.example.com/alumni",
        "event_date": (date.today() + timedelta(days=14)).isoformat(),
    }
    payload.update(overrides)
    response = await client.post("/api/v1/alumni/events", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_student_can_create_and_update_own_profile(client, db_session, organization):
    _student, headers = await _create_student_with_login(client, db_session, organization)

    create_response = await client.post(
        "/api/v1/alumni/me",
        json={"graduation_year": 2023, "current_company": "Acme Corp"},
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    assert create_response.json()["is_verified"] is False

    duplicate_response = await client.post("/api/v1/alumni/me", json={}, headers=headers)
    assert duplicate_response.status_code == 409

    update_response = await client.patch(
        "/api/v1/alumni/me", json={"current_designation": "Software Engineer"}, headers=headers
    )
    assert update_response.status_code == 200
    assert update_response.json()["current_designation"] == "Software Engineer"
    assert update_response.json()["current_company"] == "Acme Corp"


async def test_staff_without_permission_cannot_manage_alumni(client, staff_headers):
    response = await client.post(
        "/api/v1/alumni/events",
        json={"title": "Nope", "event_date": date.today().isoformat()},
        headers=staff_headers,
    )
    assert response.status_code == 403


async def test_staff_can_verify_profile(client, db_session, organization, auth_headers):
    _student, headers = await _create_student_with_login(client, db_session, organization)
    profile = (
        await client.post("/api/v1/alumni/me", json={"graduation_year": 2021}, headers=headers)
    ).json()

    profiles_response = await client.get("/api/v1/alumni/profiles", headers=auth_headers)
    assert profiles_response.status_code == 200
    assert any(p["id"] == profile["id"] for p in profiles_response.json()["items"])

    verify_response = await client.post(
        f"/api/v1/alumni/profiles/{profile['id']}/verify", json={"is_verified": True}, headers=auth_headers
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["is_verified"] is True


async def test_event_registration_requires_alumni_profile_and_published_event(
    client, db_session, organization, auth_headers
):
    event = await _create_event(client, auth_headers)  # still "draft"
    _student, headers = await _create_student_with_login(client, db_session, organization)

    # No alumni profile yet -> registering fails with not-found.
    no_profile_response = await client.post(
        f"/api/v1/alumni/events/{event['id']}/register/me", headers=headers
    )
    assert no_profile_response.status_code == 404

    await client.post("/api/v1/alumni/me", json={}, headers=headers)

    # Profile exists but event is still draft -> rejected.
    draft_response = await client.post(
        f"/api/v1/alumni/events/{event['id']}/register/me", headers=headers
    )
    assert draft_response.status_code == 422

    await client.post(
        f"/api/v1/alumni/events/{event['id']}/status", json={"status": "published"}, headers=auth_headers
    )

    list_response = await client.get("/api/v1/alumni/events/me", headers=headers)
    assert list_response.status_code == 200
    assert any(e["id"] == event["id"] for e in list_response.json())

    register_response = await client.post(
        f"/api/v1/alumni/events/{event['id']}/register/me", headers=headers
    )
    assert register_response.status_code == 201, register_response.text

    duplicate_response = await client.post(
        f"/api/v1/alumni/events/{event['id']}/register/me", headers=headers
    )
    assert duplicate_response.status_code == 409

    my_registrations_response = await client.get(
        "/api/v1/alumni/events/me/registrations", headers=headers
    )
    assert my_registrations_response.status_code == 200
    assert len(my_registrations_response.json()) == 1

    registration_id = register_response.json()["id"]
    attendance_response = await client.post(
        f"/api/v1/alumni/registrations/{registration_id}/attendance",
        json={"status": "attended"},
        headers=auth_headers,
    )
    assert attendance_response.status_code == 200
    assert attendance_response.json()["status"] == "attended"

    staff_list_response = await client.get(
        f"/api/v1/alumni/events/{event['id']}/registrations", headers=auth_headers
    )
    assert staff_list_response.status_code == 200
    assert len(staff_list_response.json()) == 1


async def test_alumni_can_post_and_update_job_referral(client, db_session, organization, auth_headers):
    _student, headers = await _create_student_with_login(client, db_session, organization)
    await client.post("/api/v1/alumni/me", json={}, headers=headers)

    create_response = await client.post(
        "/api/v1/alumni/referrals/me",
        json={"title": "Backend Engineer", "company": "Acme Corp", "contact_email": "hr@acme.com"},
        headers=headers,
    )
    assert create_response.status_code == 201, create_response.text
    referral = create_response.json()
    assert referral["status"] == "open"

    browse_response = await client.get("/api/v1/alumni/referrals", headers=headers)
    assert browse_response.status_code == 200
    assert any(r["id"] == referral["id"] for r in browse_response.json())

    close_response = await client.patch(
        f"/api/v1/alumni/referrals/me/{referral['id']}", json={"status": "closed"}, headers=headers
    )
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "closed"

    browse_after_close_response = await client.get("/api/v1/alumni/referrals", headers=headers)
    assert not any(r["id"] == referral["id"] for r in browse_after_close_response.json())

    staff_list_response = await client.get("/api/v1/alumni/referrals/all", headers=auth_headers)
    assert staff_list_response.status_code == 200
    assert any(r["id"] == referral["id"] for r in staff_list_response.json()["items"])
