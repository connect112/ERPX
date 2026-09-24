"""
API tests for the Internships module: staff CRUD for postings plus the
student self-service surface (browse open postings, apply, view/withdraw
own applications), and the "selection creates an active internship"
business rule — marking an application SELECTED must create exactly one
Internship record, which staff can then assign a mentor to.
"""

import uuid
from datetime import date, timedelta

import pytest

from modules.authentication.repository import AuthRepository
from modules.employees.repository import EmployeeRepository
from modules.students.repository import StudentRepository
from modules.users.repository import UserProfileRepository

pytestmark = pytest.mark.api


async def _create_company(client, auth_headers, **overrides):
    unique = uuid.uuid4().hex[:8]
    payload = {"name": f"Intern Corp {unique}"}
    payload.update(overrides)
    response = await client.post("/api/v1/placements/companies", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_posting(client, auth_headers, company_id, **overrides):
    payload = {
        "company_id": company_id,
        "title": "Backend Intern",
        "duration_months": 3,
        "stipend": 15000,
    }
    payload.update(overrides)
    response = await client.post("/api/v1/internships/postings", json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _create_student_with_login(client, db_session, organization, full_name="Test Student"):
    unique = uuid.uuid4().hex[:8]
    email = f"intern.{unique}@erpx.example.com"
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
    assert posting["duration_months"] == 3
    assert posting["stipend"] == 15000


async def test_staff_without_permission_cannot_manage_internships(client, staff_headers):
    response = await client.post(
        "/api/v1/internships/postings",
        json={"company_id": str(uuid.uuid4()), "title": "Nope"},
        headers=staff_headers,
    )
    assert response.status_code == 403


async def test_application_rejected_before_posting_open(client, db_session, organization, auth_headers):
    company = await _create_company(client, auth_headers)
    posting = await _create_posting(client, auth_headers, company["id"])  # still "draft"

    _student, headers = await _create_student_with_login(client, db_session, organization)
    response = await client.post(
        f"/api/v1/internships/postings/{posting['id']}/apply/me", json={}, headers=headers
    )
    assert response.status_code == 422


async def test_application_rejected_after_deadline(client, db_session, organization, auth_headers):
    company = await _create_company(client, auth_headers)
    posting = await _create_posting(
        client,
        auth_headers,
        company["id"],
        application_deadline=(date.today() - timedelta(days=1)).isoformat(),
    )
    await client.post(
        f"/api/v1/internships/postings/{posting['id']}/status", json={"status": "open"}, headers=auth_headers
    )

    _student, headers = await _create_student_with_login(client, db_session, organization)
    response = await client.post(
        f"/api/v1/internships/postings/{posting['id']}/apply/me", json={}, headers=headers
    )
    assert response.status_code == 422


async def test_student_can_apply_and_withdraw(client, db_session, organization, auth_headers):
    company = await _create_company(client, auth_headers)
    posting = await _create_posting(client, auth_headers, company["id"])
    await client.post(
        f"/api/v1/internships/postings/{posting['id']}/status", json={"status": "open"}, headers=auth_headers
    )

    _student, headers = await _create_student_with_login(client, db_session, organization)

    list_response = await client.get("/api/v1/internships/postings/me", headers=headers)
    assert list_response.status_code == 200
    assert any(p["id"] == posting["id"] for p in list_response.json())

    apply_response = await client.post(
        f"/api/v1/internships/postings/{posting['id']}/apply/me",
        json={"cover_letter": "Excited to learn backend engineering."},
        headers=headers,
    )
    assert apply_response.status_code == 201, apply_response.text
    application = apply_response.json()
    assert application["status"] == "applied"

    duplicate_response = await client.post(
        f"/api/v1/internships/postings/{posting['id']}/apply/me", json={}, headers=headers
    )
    assert duplicate_response.status_code == 409

    my_applications_response = await client.get("/api/v1/internships/applications/me", headers=headers)
    assert my_applications_response.status_code == 200
    assert len(my_applications_response.json()) == 1

    withdraw_response = await client.post(
        f"/api/v1/internships/applications/{application['id']}/withdraw/me", headers=headers
    )
    assert withdraw_response.status_code == 200
    assert withdraw_response.json()["status"] == "withdrawn"


async def test_selecting_application_creates_internship_and_mentor_can_be_assigned(
    client, db_session, organization, auth_headers
):
    company = await _create_company(client, auth_headers)
    posting = await _create_posting(client, auth_headers, company["id"])
    await client.post(
        f"/api/v1/internships/postings/{posting['id']}/status", json={"status": "open"}, headers=auth_headers
    )
    student, headers = await _create_student_with_login(client, db_session, organization)
    application = (
        await client.post(
            f"/api/v1/internships/postings/{posting['id']}/apply/me", json={}, headers=headers
        )
    ).json()

    select_response = await client.post(
        f"/api/v1/internships/applications/{application['id']}/status",
        json={"status": "selected"},
        headers=auth_headers,
    )
    assert select_response.status_code == 200
    assert select_response.json()["status"] == "selected"

    # Selecting again (e.g. re-confirming) must not create a second Internship row.
    await client.post(
        f"/api/v1/internships/applications/{application['id']}/status",
        json={"status": "selected"},
        headers=auth_headers,
    )

    internships_response = await client.get("/api/v1/internships/internships", headers=auth_headers)
    assert internships_response.status_code == 200
    matching = [i for i in internships_response.json()["items"] if i["application_id"] == application["id"]]
    assert len(matching) == 1
    internship = matching[0]
    assert internship["status"] == "ongoing"
    assert internship["stipend"] == 15000
    assert internship["mentor_employee_id"] is None

    my_internships_response = await client.get("/api/v1/internships/me", headers=headers)
    assert my_internships_response.status_code == 200
    assert len(my_internships_response.json()) == 1

    mentor = await EmployeeRepository(db_session).create(
        organization_id=organization.id,
        full_name="Mentor Employee",
        date_of_joining=date(2024, 1, 1),
    )
    await db_session.flush()

    assign_mentor_response = await client.patch(
        f"/api/v1/internships/internships/{internship['id']}",
        json={"mentor_employee_id": str(mentor.id)},
        headers=auth_headers,
    )
    assert assign_mentor_response.status_code == 200
    assert assign_mentor_response.json()["mentor_employee_id"] == str(mentor.id)

    complete_response = await client.post(
        f"/api/v1/internships/internships/{internship['id']}/status",
        json={"status": "completed"},
        headers=auth_headers,
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"
    assert complete_response.json()["end_date"] is not None
