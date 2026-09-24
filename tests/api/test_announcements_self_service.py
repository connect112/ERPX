"""
API tests for student/trainer self-service announcement reads
(modules/lms/announcements/routes.py's /me, /trainer/me) — before these,
GET /lms/announcements required lms.announcements.view, so a student or
trainer had no way to see announcements addressed to them at all, org-wide
or for their own course.
"""

import uuid
from datetime import date

import pytest

from modules.employees.repository import EmployeeRepository
from modules.trainers.repository import TrainerRepository

pytestmark = pytest.mark.api


async def _create_trainer_with_login(client, db_session, organization, full_name="Test Trainer"):
    unique = uuid.uuid4().hex[:8]
    email = f"trainer.{unique}@erpx.example.com"
    password = "TrainerPass1!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register_response.status_code == 201

    from modules.authentication.repository import AuthRepository

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)

    from modules.users.repository import UserProfileRepository

    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    employee = await EmployeeRepository(db_session).create(
        organization_id=organization.id,
        user_id=user.id,
        full_name=full_name,
        date_of_joining=date(2024, 1, 1),
    )
    trainer = await TrainerRepository(db_session).create(
        organization_id=organization.id, employee_id=employee.id
    )
    await db_session.flush()

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return trainer, {"Authorization": f"Bearer {token}"}


async def _enroll_student(client, db_session, organization, course, batch_id):
    from modules.batches.repository import BatchEnrollmentRepository
    from modules.students.repository import StudentRepository

    unique = uuid.uuid4().hex[:8]
    email = f"student.{unique}@erpx.example.com"
    password = "StudentPass1!"

    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test Student"},
    )

    from modules.authentication.repository import AuthRepository
    from modules.users.repository import UserProfileRepository

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)
    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    student = await StudentRepository(db_session).create(
        organization.id,
        user_id=user.id,
        full_name="Test Student",
        course_name=course.title,
        enrollment_date=date(2024, 1, 1),
    )
    await db_session.flush()

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    await BatchEnrollmentRepository(db_session).create(
        organization_id=organization.id,
        batch_id=uuid.UUID(batch_id),
        student_id=student.id,
        enrolled_at=date(2024, 1, 1),
    )
    await db_session.flush()
    return student, headers


@pytest.fixture
async def course(db_session, organization):
    from modules.courses.repository import CourseRepository

    unique = uuid.uuid4().hex[:8]
    return await CourseRepository(db_session).create(
        organization_id=organization.id, title="Cloud Security", slug=f"cloud-sec-{unique}"
    )


@pytest.fixture
async def other_course(db_session, organization):
    from modules.courses.repository import CourseRepository

    unique = uuid.uuid4().hex[:8]
    return await CourseRepository(db_session).create(
        organization_id=organization.id, title="Networking", slug=f"networking-{unique}"
    )


async def _create_batch(client, auth_headers, course, trainer_id):
    resp = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "trainer_id": str(trainer_id),
            "name": "Morning Batch",
            "code": f"BATCH-{uuid.uuid4().hex[:8]}",
            "start_date": "2026-09-01",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_announcement(client, auth_headers, course_id=None, title="Org update"):
    resp = await client.post(
        "/api/v1/lms/announcements",
        json={"course_id": course_id, "title": title, "body": "Body text"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_student_sees_org_wide_and_own_course_announcements_only(
    client, db_session, organization, course, other_course, auth_headers
):
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    _student, student_headers = await _enroll_student(client, db_session, organization, course, batch["id"])

    org_wide = await _create_announcement(client, auth_headers, course_id=None, title="Org wide")
    own_course = await _create_announcement(client, auth_headers, course_id=str(course.id), title="My course")
    other = await _create_announcement(client, auth_headers, course_id=str(other_course.id), title="Not mine")

    resp = await client.get("/api/v1/lms/announcements/me", headers=student_headers)
    assert resp.status_code == 200, resp.text
    ids = {a["id"] for a in resp.json()}
    assert ids == {org_wide["id"], own_course["id"]}
    assert other["id"] not in ids


async def test_trainer_sees_org_wide_and_own_course_announcements_only(
    client, db_session, organization, course, other_course, auth_headers
):
    trainer, headers = await _create_trainer_with_login(client, db_session, organization)
    await _create_batch(client, auth_headers, course, trainer.id)

    org_wide = await _create_announcement(client, auth_headers, course_id=None, title="Org wide")
    own_course = await _create_announcement(client, auth_headers, course_id=str(course.id), title="My course")
    other = await _create_announcement(client, auth_headers, course_id=str(other_course.id), title="Not mine")

    resp = await client.get("/api/v1/lms/announcements/trainer/me", headers=headers)
    assert resp.status_code == 200, resp.text
    ids = {a["id"] for a in resp.json()}
    assert ids == {org_wide["id"], own_course["id"]}
    assert other["id"] not in ids


async def test_student_cannot_post_announcements(client, db_session, organization, course, auth_headers):
    trainer, _headers = await _create_trainer_with_login(client, db_session, organization)
    batch = await _create_batch(client, auth_headers, course, trainer.id)
    _student, student_headers = await _enroll_student(client, db_session, organization, course, batch["id"])

    resp = await client.post(
        "/api/v1/lms/announcements",
        json={"course_id": None, "title": "Hijack attempt", "body": "..."},
        headers=student_headers,
    )
    assert resp.status_code == 403, resp.text


async def test_trainer_cannot_post_announcements(client, db_session, organization, auth_headers):
    _trainer, headers = await _create_trainer_with_login(client, db_session, organization)

    resp = await client.post(
        "/api/v1/lms/announcements",
        json={"course_id": None, "title": "Hijack attempt", "body": "..."},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text
