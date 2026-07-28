"""
API tests for the Placements module: staff CRUD for companies/postings
plus the student self-service surface (browse open postings, apply,
view/withdraw own applications). Applications are unique per
(posting, student), so duplicate-apply and cross-student isolation are
the key edge cases alongside the happy path.
"""

import uuid
from datetime import date, timedelta

import pytest

from modules.authentication.repository import AuthRepository
from modules.students.repository import StudentRepository
from modules.users.repository import UserProfileRepository

pytestmark = pytest.mark.api


async def _create_company(client, auth_headers, **overrides):
    unique = uuid.uuid4().hex[:8]
    payload = {"name": f"Acme Corp {unique}"}
    payload.update(overrides)
    response = await client.post("/api/v1/placements/companies", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_posting(client, auth_headers, company_id, **overrides):
    payload = {
        "company_id": company_id,
        "title": "Software Engineer",
        "job_type": "full_time",
    }
    payload.update(overrides)
    response = await client.post("/api/v1/placements/postings", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_student_with_login(client, db_session, organization, full_name="Test Student"):
    unique = uuid.uuid4().hex[:8]
    email = f"placement.{unique}@erpx.example.com"
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
        enrollment_date=date(2026, 1, 1),
    )
    await db_session.flush()

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return student, {"Authorization": f"Bearer {token}"}


async def test_create_company_and_posting(client, auth_headers):
    company = await _create_company(client, auth_headers)
    posting = await _create_posting(client, auth_headers, company["id"])
    assert posting["status"] == "draft"
    assert posting["company_id"] == company["id"]


async def test_staff_without_permission_cannot_manage_placements(client, staff_headers):
    response = await client.post(
        "/api/v1/placements/companies", json={"name": "Unauthorized Co"}, headers=staff_headers
    )
    assert response.status_code == 403


async def test_application_rejected_before_posting_open(client, db_session, organization, auth_headers):
    company = await _create_company(client, auth_headers)
    posting = await _create_posting(client, auth_headers, company["id"])  # still "draft"

    _student, headers = await _create_student_with_login(client, db_session, organization)
    response = await client.post(
        f"/api/v1/placements/postings/{posting['id']}/apply/me", json={}, headers=headers
    )
    assert response.status_code == 422


async def test_student_can_apply_and_withdraw(client, db_session, organization, auth_headers):
    company = await _create_company(client, auth_headers)
    posting = await _create_posting(client, auth_headers, company["id"])
    await client.post(
        f"/api/v1/placements/postings/{posting['id']}/status", json={"status": "open"}, headers=auth_headers
    )

    _student, headers = await _create_student_with_login(client, db_session, organization)

    list_response = await client.get("/api/v1/placements/postings/me", headers=headers)
    assert list_response.status_code == 200
    assert any(p["id"] == posting["id"] for p in list_response.json())

    apply_response = await client.post(
        f"/api/v1/placements/postings/{posting['id']}/apply/me",
        json={"cover_letter": "I would love to join your team."},
        headers=headers,
    )
    assert apply_response.status_code == 201, apply_response.text
    application = apply_response.json()
    assert application["status"] == "applied"

    duplicate_response = await client.post(
        f"/api/v1/placements/postings/{posting['id']}/apply/me", json={}, headers=headers
    )
    assert duplicate_response.status_code == 409

    my_applications_response = await client.get("/api/v1/placements/applications/me", headers=headers)
    assert my_applications_response.status_code == 200
    assert len(my_applications_response.json()) == 1

    withdraw_response = await client.post(
        f"/api/v1/placements/applications/{application['id']}/withdraw/me", headers=headers
    )
    assert withdraw_response.status_code == 200
    assert withdraw_response.json()["status"] == "withdrawn"


async def test_application_rejected_after_deadline(client, db_session, organization, auth_headers):
    company = await _create_company(client, auth_headers)
    posting = await _create_posting(
        client,
        auth_headers,
        company["id"],
        application_deadline=(date.today() - timedelta(days=1)).isoformat(),
    )
    await client.post(
        f"/api/v1/placements/postings/{posting['id']}/status", json={"status": "open"}, headers=auth_headers
    )

    _student, headers = await _create_student_with_login(client, db_session, organization)
    response = await client.post(
        f"/api/v1/placements/postings/{posting['id']}/apply/me", json={}, headers=headers
    )
    assert response.status_code == 422


async def test_staff_can_list_applications_and_change_status(client, db_session, organization, auth_headers):
    company = await _create_company(client, auth_headers)
    posting = await _create_posting(client, auth_headers, company["id"])
    await client.post(
        f"/api/v1/placements/postings/{posting['id']}/status", json={"status": "open"}, headers=auth_headers
    )
    _student, headers = await _create_student_with_login(client, db_session, organization)
    application = (
        await client.post(f"/api/v1/placements/postings/{posting['id']}/apply/me", json={}, headers=headers)
    ).json()

    applications_response = await client.get(
        f"/api/v1/placements/postings/{posting['id']}/applications", headers=auth_headers
    )
    assert applications_response.status_code == 200
    assert len(applications_response.json()) == 1

    status_response = await client.post(
        f"/api/v1/placements/applications/{application['id']}/status",
        json={"status": "shortlisted", "notes": "Strong candidate."},
        headers=auth_headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "shortlisted"
    assert status_response.json()["notes"] == "Strong candidate."
