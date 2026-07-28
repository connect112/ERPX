"""
API tests for trainer self-service ("me") endpoints — the foundation the
trainer portal depends on. A trainer's ownership chain is
User -> Employee (Employee.user_id) -> Trainer (Trainer.employee_id).
These verify a logged-in trainer sees their own batches/attendance and
can grade submissions only for courses they actually teach (ownership,
not RBAC permission), and critically that they can't act on another
trainer's batches or a course they don't teach.
"""

import uuid
from datetime import date, datetime, timezone

import pytest

from modules.courses.repository import CourseRepository
from modules.employees.repository import EmployeeRepository
from modules.lms.assignments.repository import AssignmentRepository, SubmissionRepository
from modules.students.repository import StudentRepository
from modules.trainers.repository import TrainerRepository

pytestmark = pytest.mark.api


@pytest.fixture
def register_payload():
    return {
        "email": "no.trainer.link@erpx.example.com",
        "password": "StrongPass1!",
        "full_name": "No Trainer Link",
    }


async def _create_trainer_with_login(client, db_session, organization, full_name="Test Trainer"):
    """Registers a real user, verifies them, then links an Employee + Trainer profile to that user."""
    unique = uuid.uuid4().hex[:8]
    email = f"trainer.{unique}@erpx.example.com"
    password = "TrainerPass1!"

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

    employee = await EmployeeRepository(db_session).create(
        organization_id=organization.id,
        user_id=user.id,
        employee_code=f"EMP-{unique}",
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


@pytest.fixture
async def course(db_session, organization):
    repo = CourseRepository(db_session)
    unique = uuid.uuid4().hex[:8]
    return await repo.create(
        organization_id=organization.id, title="Data Engineering", slug=f"data-eng-{unique}"
    )


async def test_trainer_can_view_own_profile(client, db_session, organization):
    trainer, headers = await _create_trainer_with_login(client, db_session, organization)

    response = await client.get("/api/v1/trainers/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(trainer.id)
    assert response.json()["employee_name"] == "Test Trainer"


async def test_user_without_linked_employee_gets_clear_error(client, register_payload, db_session):
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

    response = await client.get("/api/v1/trainers/me", headers=headers)
    assert response.status_code == 422


async def test_trainer_without_permission_cannot_create_batches(
    client, db_session, organization, course
):
    trainer, headers = await _create_trainer_with_login(client, db_session, organization)

    create_response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "trainer_id": str(trainer.id),
            "name": "Evening Batch",
            "code": f"BATCH-{uuid.uuid4().hex[:8]}",
            "start_date": "2026-09-01",
        },
        headers=headers,
    )
    assert create_response.status_code == 403  # trainer has no batches.manage permission


async def test_trainer_cannot_see_another_trainers_batches(
    client, db_session, organization, course, auth_headers
):
    trainer_a, headers_a = await _create_trainer_with_login(
        client, db_session, organization, full_name="Trainer A"
    )
    trainer_b, _headers_b = await _create_trainer_with_login(
        client, db_session, organization, full_name="Trainer B"
    )

    # Only trainer B is assigned to this batch.
    batch_response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "trainer_id": trainer_b.id.__str__(),
            "name": "Weekend Batch",
            "code": f"BATCH-{uuid.uuid4().hex[:8]}",
            "start_date": "2026-09-01",
        },
        headers=auth_headers,
    )
    assert batch_response.status_code == 201

    response_a = await client.get("/api/v1/batches/me", headers=headers_a)
    assert response_a.status_code == 200
    assert response_a.json() == []

    response_b = await client.get("/api/v1/batches/me", headers=_headers_b)
    assert response_b.status_code == 200
    assert len(response_b.json()) == 1
    assert response_b.json()[0]["id"] == batch_response.json()["id"]
    assert response_b.json()[0]["course_title"] == course.title

    response_b = await client.get("/api/v1/batches/me", headers=_headers_b)
    assert response_b.status_code == 200
    assert len(response_b.json()) == 1
    assert response_b.json()[0]["id"] == batch_response.json()["id"]


async def test_trainer_can_grade_submission_for_course_they_teach(
    client, db_session, organization, course, auth_headers
):
    trainer, headers = await _create_trainer_with_login(client, db_session, organization)

    batch_response = await client.post(
        "/api/v1/batches",
        json={
            "course_id": str(course.id),
            "trainer_id": str(trainer.id),
            "name": "Morning Batch",
            "code": f"BATCH-{uuid.uuid4().hex[:8]}",
            "start_date": "2026-09-01",
        },
        headers=auth_headers,
    )
    assert batch_response.status_code == 201

    assignment = await AssignmentRepository(db_session).create(
        course_id=course.id, title="Homework 1", max_score=100
    )
    student = await StudentRepository(db_session).create(
        organization.id,
        full_name="Grading Target Student",
        course_name=course.title,
        enrollment_date=date(2026, 1, 1),
    )
    submission = await SubmissionRepository(db_session).create(
        assignment_id=assignment.id,
        student_id=student.id,
        content_text="my answer",
        submitted_at=datetime.now(timezone.utc),
    )
    await db_session.flush()

    # Trainer teaches this course (has a batch) -> can list + grade.
    list_response = await client.get(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/me", headers=headers
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["student_name"] == "Grading Target Student"

    grade_response = await client.post(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/{submission.id}/grade/me",
        json={"score": 90, "feedback": "Great work"},
        headers=headers,
    )
    assert grade_response.status_code == 200
    assert grade_response.json()["score"] == 90
    assert grade_response.json()["status"] == "graded"


async def test_trainer_cannot_grade_submission_for_course_they_dont_teach(
    client, db_session, organization, course
):
    _trainer, headers = await _create_trainer_with_login(client, db_session, organization)
    # No batch created for this trainer on this course.

    assignment = await AssignmentRepository(db_session).create(
        course_id=course.id, title="Homework 2", max_score=100
    )
    student = await StudentRepository(db_session).create(
        organization.id,
        full_name="Untaught Course Student",
        course_name=course.title,
        enrollment_date=date(2026, 1, 1),
    )
    submission = await SubmissionRepository(db_session).create(
        assignment_id=assignment.id,
        student_id=student.id,
        content_text="answer",
        submitted_at=datetime.now(timezone.utc),
    )
    await db_session.flush()

    list_response = await client.get(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/me", headers=headers
    )
    assert list_response.status_code == 403

    grade_response = await client.post(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/{submission.id}/grade/me",
        json={"score": 50, "feedback": "N/A"},
        headers=headers,
    )
    assert grade_response.status_code == 403


async def test_trainer_can_check_in_and_out_and_see_own_attendance(client, db_session, organization):
    _trainer, headers = await _create_trainer_with_login(client, db_session, organization)

    check_in_response = await client.post("/api/v1/attendance/check-in/me", json={}, headers=headers)
    assert check_in_response.status_code == 201, check_in_response.text
    assert check_in_response.json()["status"] == "present"
    assert check_in_response.json()["check_in_time"] is not None

    check_out_response = await client.post("/api/v1/attendance/check-out/me", json={}, headers=headers)
    assert check_out_response.status_code == 200
    assert check_out_response.json()["check_out_time"] is not None

    history_response = await client.get("/api/v1/attendance/me", headers=headers)
    assert history_response.status_code == 200
    body = history_response.json()
    assert body["total"] == 1
    assert body["items"][0]["check_out_time"] is not None
