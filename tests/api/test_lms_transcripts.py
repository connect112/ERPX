"""
API tests for LMS Transcripts — a read-only aggregator (no dedicated
table) combining Enrollment, Progress, Results, and Certificates into
one per-student view. Both the student self-service "me" endpoint and
the staff-facing by-id endpoint are covered.
"""

import uuid
from datetime import date

import pytest

from modules.courses.chapters.repository import ChapterRepository
from modules.courses.lessons.repository import LessonRepository
from modules.courses.repository import CourseRepository
from modules.lms.certificates.repository import CertificateRepository
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.lms.progress.repository import ProgressRepository
from modules.students.repository import StudentRepository

pytestmark = pytest.mark.api


async def _create_student_with_login(client, db_session, organization, full_name="Test Student"):
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


async def test_student_sees_own_transcript_with_certificate_and_progress(
    client, db_session, organization
):
    student, headers = await _create_student_with_login(client, db_session, organization)

    course = await CourseRepository(db_session).create(
        organization_id=organization.id, title="Linear Algebra", slug=f"la-{uuid.uuid4().hex[:8]}"
    )
    chapter = await ChapterRepository(db_session).create(
        course_id=course.id, title="Vectors", order_index=1
    )
    lesson = await LessonRepository(db_session).create(
        chapter_id=chapter.id, title="Dot Product", order_index=1
    )
    await EnrollmentRepository(db_session).create(
        student_id=student.id, course_id=course.id, enrolled_on=date(2026, 1, 5)
    )
    await ProgressRepository(db_session).mark_complete(student.id, lesson.id)
    await CertificateRepository(db_session).create(
        student_id=student.id, course_id=course.id, certificate_number=f"ERPX-CERT-{uuid.uuid4().hex[:8].upper()}"
    )
    await db_session.flush()

    response = await client.get("/api/v1/lms/transcripts/me", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["student_id"] == str(student.id)
    assert body["total_courses"] == 1
    assert body["certificates_earned"] == 1

    entry = body["courses"][0]
    assert entry["course_id"] == str(course.id)
    assert entry["percent_complete"] == 100.0
    assert entry["certificate_number"] is not None
    assert entry["result"] is None  # no exam/practical/viva components for this course


async def test_staff_can_view_student_transcript_by_id(client, db_session, organization, auth_headers):
    student, _headers = await _create_student_with_login(client, db_session, organization)

    response = await client.get(f"/api/v1/lms/transcripts/{student.id}", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["student_id"] == str(student.id)


async def test_staff_without_permission_cannot_view_transcript(client, db_session, organization, staff_headers):
    student, _headers = await _create_student_with_login(client, db_session, organization)

    response = await client.get(f"/api/v1/lms/transcripts/{student.id}", headers=staff_headers)
    assert response.status_code == 403
