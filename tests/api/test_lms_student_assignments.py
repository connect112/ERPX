"""
API tests for the student self-service assignment-submission routes
(`.../submissions/mine`) — ownership-gated via `get_current_student`, no
permission code involved, mirroring the `/apply/me`-style convention used
elsewhere in this codebase (see modules/placements). No test file existed
for this before (confirmed) — the staff/on-behalf-of submission route
(`POST .../submissions`, gated by `lms.assignments.submit`) already has no
dedicated test file either; these tests cover the new self-service surface
only, not a general regression suite for the whole assignments module.
"""

import uuid
from datetime import date, datetime, timezone

import pytest

from modules.courses.repository import CourseRepository
from modules.lms.assignments.repository import AssignmentRepository
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.students.repository import StudentRepository

pytestmark = pytest.mark.api


@pytest.fixture
async def course(db_session, organization):
    unique = uuid.uuid4().hex[:8]
    return await CourseRepository(db_session).create(
        organization_id=organization.id, title="Data Engineering", slug=f"data-eng-{unique}"
    )


async def _create_student_with_login(client, db_session, organization, full_name="Test Student"):
    unique = uuid.uuid4().hex[:8]
    email = f"lms.student.{unique}@erpx.example.com"
    password = "StudentPass1!"

    register_response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert register_response.status_code == 201

    from modules.authentication.repository import AuthRepository
    from modules.users.repository import UserProfileRepository

    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)
    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)

    student = await StudentRepository(db_session).create(
        organization.id,
        user_id=user.id,
        full_name=full_name,
        course_name="Data Engineering",
        enrollment_date=date(2026, 1, 1),
    )
    await db_session.flush()

    login_response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return student, {"Authorization": f"Bearer {token}"}


async def test_student_can_submit_own_assignment(client, db_session, organization, course):
    student, headers = await _create_student_with_login(client, db_session, organization)
    await EnrollmentRepository(db_session).create(
        student_id=student.id, course_id=course.id, enrolled_on=date(2026, 1, 1)
    )
    assignment = await AssignmentRepository(db_session).create(
        course_id=course.id, title="Homework 1", max_score=100
    )
    await db_session.flush()

    response = await client.post(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/mine",
        json={"content_text": "my answer"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["student_id"] == str(student.id)
    assert body["content_text"] == "my answer"
    assert body["status"] == "submitted"


async def test_student_cannot_submit_twice(client, db_session, organization, course):
    student, headers = await _create_student_with_login(client, db_session, organization)
    await EnrollmentRepository(db_session).create(
        student_id=student.id, course_id=course.id, enrolled_on=date(2026, 1, 1)
    )
    assignment = await AssignmentRepository(db_session).create(
        course_id=course.id, title="Homework 1", max_score=100
    )
    await db_session.flush()

    first = await client.post(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/mine",
        json={"content_text": "attempt 1"},
        headers=headers,
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/mine",
        json={"content_text": "attempt 2"},
        headers=headers,
    )
    assert second.status_code == 409


async def test_student_not_enrolled_cannot_submit(client, db_session, organization, course):
    student, headers = await _create_student_with_login(client, db_session, organization)
    # Deliberately no Enrollment row created for this student/course.
    assignment = await AssignmentRepository(db_session).create(
        course_id=course.id, title="Homework 1", max_score=100
    )
    await db_session.flush()

    response = await client.post(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/mine",
        json={"content_text": "sneaky answer"},
        headers=headers,
    )
    assert response.status_code == 403


async def test_get_my_submission_404s_before_submitting_then_200s_after(
    client, db_session, organization, course
):
    student, headers = await _create_student_with_login(client, db_session, organization)
    await EnrollmentRepository(db_session).create(
        student_id=student.id, course_id=course.id, enrolled_on=date(2026, 1, 1)
    )
    assignment = await AssignmentRepository(db_session).create(
        course_id=course.id, title="Homework 1", max_score=100
    )
    await db_session.flush()

    before = await client.get(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/mine", headers=headers
    )
    assert before.status_code == 404

    submit = await client.post(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/mine",
        json={"content_text": "my answer"},
        headers=headers,
    )
    assert submit.status_code == 201

    after = await client.get(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/mine", headers=headers
    )
    assert after.status_code == 200
    assert after.json()["content_text"] == "my answer"


async def test_another_students_submission_is_not_visible_as_mine(
    client, db_session, organization, course
):
    """A second student, also enrolled, must see their own (absent)
    submission via /mine — not the first student's."""
    student_a, headers_a = await _create_student_with_login(client, db_session, organization, "Student A")
    student_b, headers_b = await _create_student_with_login(client, db_session, organization, "Student B")
    for student in (student_a, student_b):
        await EnrollmentRepository(db_session).create(
            student_id=student.id, course_id=course.id, enrolled_on=date(2026, 1, 1)
        )
    assignment = await AssignmentRepository(db_session).create(
        course_id=course.id, title="Homework 1", max_score=100
    )
    await db_session.flush()

    submit_a = await client.post(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/mine",
        json={"content_text": "student A's answer"},
        headers=headers_a,
    )
    assert submit_a.status_code == 201

    mine_b = await client.get(
        f"/api/v1/lms/courses/{course.id}/assignments/{assignment.id}/submissions/mine", headers=headers_b
    )
    assert mine_b.status_code == 404
