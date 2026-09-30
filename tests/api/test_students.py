"""
API tests for admin-facing student login provisioning
(`POST /students/{id}/create-login-account`, `POST /students/{id}/resend-login-email`)
-- the general-purpose counterpart to modules/provisioning's Pentrix-only,
payment-webhook-triggered flow. This activates an *existing* Student
record (created directly or via CRM admission) rather than creating one.
"""

import uuid
from datetime import date

import pytest

from modules.batches.models import BatchStatus
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.courses.repository import CourseRepository
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.students.repository import StudentRepository

pytestmark = pytest.mark.api


async def _create_course(db_session, organization, title="Test Course"):
    unique = uuid.uuid4().hex[:8]
    return await CourseRepository(db_session).create(
        organization_id=organization.id, title=title, slug=f"course-{unique}", is_published=True
    )


async def _create_student(db_session, organization, *, email="new.student@erpx.example.com", user_id=None):
    return await StudentRepository(db_session).create(
        organization.id,
        full_name="New Student",
        email=email,
        course_name="Some Program",
        enrollment_date=date(2026, 1, 1),
        user_id=user_id,
    )


@pytest.fixture(autouse=True)
def _no_background_login_email(monkeypatch):
    import modules.students.service as students_service_module

    monkeypatch.setattr(students_service_module.send_password_reset_email_task, "delay", lambda *a, **kw: None)


async def test_create_login_account_happy_path(client, auth_headers, db_session, organization, rbac_seeded):
    student = await _create_student(db_session, organization)
    course = await _create_course(db_session, organization)

    resp = await client.post(
        f"/api/v1/students/{student.id}/create-login-account",
        json={"course_id": str(course.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "created"
    assert body["login_url"]
    assert uuid.UUID(body["user_id"])

    refreshed = await StudentRepository(db_session).get_by_id(student.id, organization.id)
    assert refreshed.user_id is not None

    enrollment = await EnrollmentRepository(db_session).get_by_student_and_course(student.id, course.id)
    assert enrollment is not None


async def test_create_login_account_rejects_if_already_has_login(
    client, auth_headers, db_session, organization, rbac_seeded, superuser
):
    existing_user, _ = superuser
    student = await _create_student(db_session, organization, user_id=existing_user.id)
    course = await _create_course(db_session, organization)

    resp = await client.post(
        f"/api/v1/students/{student.id}/create-login-account",
        json={"course_id": str(course.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 409, resp.text


async def test_create_login_account_rejects_missing_email(
    client, auth_headers, db_session, organization, rbac_seeded
):
    student = await _create_student(db_session, organization, email=None)
    course = await _create_course(db_session, organization)

    resp = await client.post(
        f"/api/v1/students/{student.id}/create-login-account",
        json={"course_id": str(course.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text


async def test_create_login_account_rejects_email_collision(
    client, auth_headers, db_session, organization, rbac_seeded
):
    collision_email = f"collide.{uuid.uuid4().hex[:8]}@erpx.example.com"
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={"email": collision_email, "password": "SomePass1!", "full_name": "Someone Else"},
    )
    assert register_resp.status_code == 201

    student = await _create_student(db_session, organization, email=collision_email)
    course = await _create_course(db_session, organization)

    resp = await client.post(
        f"/api/v1/students/{student.id}/create-login-account",
        json={"course_id": str(course.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 409, resp.text


async def test_create_login_account_rejects_batch_from_a_different_course(
    client, auth_headers, db_session, organization, rbac_seeded
):
    student = await _create_student(db_session, organization)
    course = await _create_course(db_session, organization)
    other_course = await _create_course(db_session, organization, title="Other Course")
    batch = await BatchRepository(db_session).create(
        organization_id=organization.id,
        course_id=other_course.id,
        code=f"BATCH-{uuid.uuid4().hex[:6]}",
        name="Mismatched Batch",
        status=BatchStatus.ONGOING,
        start_date=date(2026, 1, 1),
    )

    resp = await client.post(
        f"/api/v1/students/{student.id}/create-login-account",
        json={"course_id": str(course.id), "batch_id": str(batch.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text


async def test_create_login_account_with_explicit_batch(
    client, auth_headers, db_session, organization, rbac_seeded
):
    student = await _create_student(db_session, organization)
    course = await _create_course(db_session, organization)
    batch = await BatchRepository(db_session).create(
        organization_id=organization.id,
        course_id=course.id,
        code=f"BATCH-{uuid.uuid4().hex[:6]}",
        name="Evening Batch",
        status=BatchStatus.ONGOING,
        start_date=date(2026, 1, 1),
    )

    resp = await client.post(
        f"/api/v1/students/{student.id}/create-login-account",
        json={"course_id": str(course.id), "batch_id": str(batch.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text

    batch_enrollment = await BatchEnrollmentRepository(db_session).get_by_batch_and_student(
        batch.id, student.id
    )
    assert batch_enrollment is not None


async def test_resend_login_email_requires_existing_login(
    client, auth_headers, db_session, organization, rbac_seeded
):
    student = await _create_student(db_session, organization)

    resp = await client.post(
        f"/api/v1/students/{student.id}/resend-login-email", headers=auth_headers
    )
    assert resp.status_code == 422, resp.text


async def test_resend_login_email_happy_path(client, auth_headers, db_session, organization, rbac_seeded):
    student = await _create_student(db_session, organization)
    course = await _create_course(db_session, organization)

    create_resp = await client.post(
        f"/api/v1/students/{student.id}/create-login-account",
        json={"course_id": str(course.id)},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200, create_resp.text

    resend_resp = await client.post(
        f"/api/v1/students/{student.id}/resend-login-email", headers=auth_headers
    )
    assert resend_resp.status_code == 200, resend_resp.text
