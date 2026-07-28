"""
API tests for student self-service ("me") endpoints — the foundation the
student portal depends on. These verify a logged-in student sees their
own enrollments/progress/profile without needing any RBAC permission
(ownership is the authorization), and critically that they can never see
another student's data through the same endpoints.
"""

import uuid
from datetime import date

import pytest

from modules.courses.repository import CourseRepository
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.students.repository import StudentRepository

pytestmark = pytest.mark.api


@pytest.fixture
def register_payload():
    return {
        "email": "no.student.link@erpx.example.com",
        "password": "StrongPass1!",
        "full_name": "No Student Link",
    }


async def _create_student_with_login(client, db_session, organization, full_name="Test Student"):
    """Registers a real user, verifies them, then links a Student record to that user."""
    unique = uuid.uuid4().hex[:8]
    email = f"student.{unique}@erpx.example.com"
    password = "StudentPass1!"

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

    student_repo = StudentRepository(db_session)
    student = await student_repo.create(
        organization.id,
        user_id=user.id,
        full_name=full_name,
        course_name="Python Bootcamp",
        enrollment_date=date(2026, 1, 1),
    )
    await db_session.flush()

    login_response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    return student, {"Authorization": f"Bearer {token}"}


async def test_student_can_view_own_profile(client, db_session, organization):
    student, headers = await _create_student_with_login(client, db_session, organization)

    response = await client.get("/api/v1/students/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(student.id)
    assert response.json()["full_name"] == "Test Student"


async def test_user_without_linked_student_gets_clear_error(client, register_payload, db_session):
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

    response = await client.get("/api/v1/students/me", headers=headers)
    assert response.status_code == 422


async def test_student_sees_own_enrollments_via_me_endpoint(client, db_session, organization):
    student, headers = await _create_student_with_login(client, db_session, organization)

    course = await CourseRepository(db_session).create(
        organization_id=organization.id, title="Data Structures", slug=f"ds-{uuid.uuid4().hex[:8]}"
    )
    await EnrollmentRepository(db_session).create(
        student_id=student.id, course_id=course.id, enrolled_on=date(2026, 1, 5)
    )
    await db_session.flush()

    response = await client.get("/api/v1/lms/enrollment/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["course_id"] == str(course.id)


async def test_student_cannot_see_another_students_enrollments(client, db_session, organization):
    student_a, headers_a = await _create_student_with_login(
        client, db_session, organization, full_name="Student A"
    )
    student_b, _headers_b = await _create_student_with_login(
        client, db_session, organization, full_name="Student B"
    )

    course = await CourseRepository(db_session).create(
        organization_id=organization.id, title="Networking", slug=f"net-{uuid.uuid4().hex[:8]}"
    )
    # Only student B is enrolled.
    await EnrollmentRepository(db_session).create(
        student_id=student_b.id, course_id=course.id, enrolled_on=date(2026, 1, 5)
    )
    await db_session.flush()

    # Student A's own "me" view must come back empty, not see B's enrollment.
    response = await client.get("/api/v1/lms/enrollment/me", headers=headers_a)
    assert response.status_code == 200
    assert response.json() == []


async def test_student_can_mark_own_lesson_complete_and_see_progress(client, db_session, organization):
    from modules.courses.chapters.repository import ChapterRepository
    from modules.courses.lessons.repository import LessonRepository

    student, headers = await _create_student_with_login(client, db_session, organization)

    course = await CourseRepository(db_session).create(
        organization_id=organization.id, title="Algorithms", slug=f"algo-{uuid.uuid4().hex[:8]}"
    )
    chapter = await ChapterRepository(db_session).create(
        course_id=course.id, title="Sorting", order_index=1
    )
    lesson = await LessonRepository(db_session).create(
        chapter_id=chapter.id, title="Quicksort", order_index=1
    )
    await db_session.flush()

    complete_response = await client.post(
        f"/api/v1/lms/progress/me/complete/{lesson.id}", headers=headers
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["lesson_id"] == str(lesson.id)

    progress_response = await client.get(
        f"/api/v1/lms/progress/me/course/{course.id}", headers=headers
    )
    assert progress_response.status_code == 200
    body = progress_response.json()
    assert body["total_lessons"] == 1
    assert body["completed_lessons"] == 1
    assert body["percent_complete"] == 100.0


async def test_enrolled_student_can_view_course_chapters_and_lessons(client, db_session, organization):
    from modules.courses.chapters.repository import ChapterRepository
    from modules.courses.lessons.repository import LessonRepository

    student, headers = await _create_student_with_login(client, db_session, organization)

    course = await CourseRepository(db_session).create(
        organization_id=organization.id, title="Operating Systems", slug=f"os-{uuid.uuid4().hex[:8]}"
    )
    chapter = await ChapterRepository(db_session).create(
        course_id=course.id, title="Processes", order_index=1
    )
    lesson = await LessonRepository(db_session).create(
        chapter_id=chapter.id, title="Scheduling", order_index=1
    )
    await EnrollmentRepository(db_session).create(
        student_id=student.id, course_id=course.id, enrolled_on=date(2026, 1, 5)
    )
    await db_session.flush()

    course_response = await client.get(f"/api/v1/courses/{course.id}/me", headers=headers)
    assert course_response.status_code == 200
    assert course_response.json()["id"] == str(course.id)

    chapters_response = await client.get(
        f"/api/v1/courses/{course.id}/chapters/me", headers=headers
    )
    assert chapters_response.status_code == 200
    chapters_body = chapters_response.json()
    assert len(chapters_body) == 1
    assert chapters_body[0]["id"] == str(chapter.id)

    lessons_response = await client.get(
        f"/api/v1/courses/{course.id}/chapters/{chapter.id}/lessons/me", headers=headers
    )
    assert lessons_response.status_code == 200
    lessons_body = lessons_response.json()
    assert len(lessons_body) == 1
    assert lessons_body[0]["id"] == str(lesson.id)


async def test_unenrolled_student_cannot_view_course_content(client, db_session, organization):
    from modules.courses.chapters.repository import ChapterRepository
    from modules.courses.lessons.repository import LessonRepository

    _student, headers = await _create_student_with_login(client, db_session, organization)

    course = await CourseRepository(db_session).create(
        organization_id=organization.id, title="Compilers", slug=f"comp-{uuid.uuid4().hex[:8]}"
    )
    chapter = await ChapterRepository(db_session).create(
        course_id=course.id, title="Parsing", order_index=1
    )
    lesson = await LessonRepository(db_session).create(
        chapter_id=chapter.id, title="LL(1)", order_index=1
    )
    await db_session.flush()
    # No enrollment created for this student.

    course_response = await client.get(f"/api/v1/courses/{course.id}/me", headers=headers)
    assert course_response.status_code == 403

    chapters_response = await client.get(
        f"/api/v1/courses/{course.id}/chapters/me", headers=headers
    )
    assert chapters_response.status_code == 403

    lessons_response = await client.get(
        f"/api/v1/courses/{course.id}/chapters/{chapter.id}/lessons/me", headers=headers
    )
    assert lessons_response.status_code == 403
