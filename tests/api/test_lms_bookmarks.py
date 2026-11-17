"""
API tests for LMS lesson bookmarks — a student self-service ("me")
feature, ownership-based like the rest of the student self-service
surface, no RBAC permission required.
"""

import uuid
from datetime import date

import pytest

from modules.courses.chapters.repository import ChapterRepository
from modules.courses.lessons.repository import LessonRepository
from modules.courses.repository import CourseRepository
from modules.lms.enrollment.models import EnrollmentStatus
from modules.lms.enrollment.repository import EnrollmentRepository
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


async def _create_lesson(db_session, organization, *enrolled_students):
    """A lesson in a new course; the given students are enrolled in that course (a student may bookmark only lessons of a course they are in)."""
    course = await CourseRepository(db_session).create(
        organization_id=organization.id, title="Discrete Math", slug=f"dm-{uuid.uuid4().hex[:8]}"
    )
    chapter = await ChapterRepository(db_session).create(
        course_id=course.id, title="Sets", order_index=1
    )
    lesson = await LessonRepository(db_session).create(
        chapter_id=chapter.id, title="Set Operations", order_index=1
    )
    for student in enrolled_students:
        await EnrollmentRepository(db_session).create(student_id=student.id, course_id=course.id, enrolled_on=date.today())
    await db_session.flush()
    return course, lesson


async def test_student_can_bookmark_and_list_lesson(client, db_session, organization):
    _student, headers = await _create_student_with_login(client, db_session, organization)
    course, lesson = await _create_lesson(db_session, organization, _student)

    create_response = await client.post(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers)
    assert create_response.status_code == 201, create_response.text

    list_response = await client.get("/api/v1/lms/bookmarks/me", headers=headers)
    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body) == 1
    assert body[0]["lesson_id"] == str(lesson.id)
    assert body[0]["course_id"] == str(course.id)


async def test_bookmarking_same_lesson_twice_conflicts(client, db_session, organization):
    _student, headers = await _create_student_with_login(client, db_session, organization)
    _course, lesson = await _create_lesson(db_session, organization, _student)

    first = await client.post(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers)
    assert first.status_code == 201

    second = await client.post(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers)
    assert second.status_code == 409


async def test_student_can_remove_own_bookmark(client, db_session, organization):
    _student, headers = await _create_student_with_login(client, db_session, organization)
    _course, lesson = await _create_lesson(db_session, organization, _student)

    await client.post(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers)

    delete_response = await client.delete(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers)
    assert delete_response.status_code == 200

    list_response = await client.get("/api/v1/lms/bookmarks/me", headers=headers)
    assert list_response.json() == []


async def test_removing_nonexistent_bookmark_returns_404(client, db_session, organization):
    _student, headers = await _create_student_with_login(client, db_session, organization)
    _course, lesson = await _create_lesson(db_session, organization)

    response = await client.delete(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers)
    assert response.status_code == 404


async def test_student_only_sees_own_bookmarks(client, db_session, organization):
    _student_a, headers_a = await _create_student_with_login(
        client, db_session, organization, full_name="Student A"
    )
    _student_b, headers_b = await _create_student_with_login(
        client, db_session, organization, full_name="Student B"
    )
    _course, lesson = await _create_lesson(db_session, organization, _student_a, _student_b)

    await client.post(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers_b)

    response_a = await client.get("/api/v1/lms/bookmarks/me", headers=headers_a)
    assert response_a.json() == []

    response_b = await client.get("/api/v1/lms/bookmarks/me", headers=headers_b)
    assert len(response_b.json()) == 1


# ---- a bookmark never opens a door the enrolment has closed (see modules/lms/enrollment/access.py)


async def test_a_student_cannot_bookmark_a_lesson_of_a_course_they_are_not_in(client, db_session, organization):
    _student, headers = await _create_student_with_login(client, db_session, organization)
    _course, lesson = await _create_lesson(db_session, organization)  # nobody is enrolled

    response = await client.post(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers)
    assert response.status_code == 403
    assert (await client.get("/api/v1/lms/bookmarks/me", headers=headers)).json() == []


async def test_a_lesson_of_another_organization_or_that_does_not_exist_is_simply_not_found(client, db_session, organization):
    from modules.organizations.repository import OrganizationRepository

    _student, headers = await _create_student_with_login(client, db_session, organization)
    other = await OrganizationRepository(db_session).create(name="Other Org", slug=f"other-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    _course, foreign_lesson = await _create_lesson(db_session, other)

    assert (await client.post(f"/api/v1/lms/bookmarks/me/{foreign_lesson.id}", headers=headers)).status_code == 404
    assert (await client.post(f"/api/v1/lms/bookmarks/me/{uuid.uuid4()}", headers=headers)).status_code == 404
    assert (await client.get("/api/v1/lms/bookmarks/me", headers=headers)).json() == []


async def test_an_enrolment_in_one_course_does_not_allow_bookmarking_another(client, db_session, organization):
    student, headers = await _create_student_with_login(client, db_session, organization)
    _mine, my_lesson = await _create_lesson(db_session, organization, student)
    _other, other_lesson = await _create_lesson(db_session, organization)

    assert (await client.post(f"/api/v1/lms/bookmarks/me/{my_lesson.id}", headers=headers)).status_code == 201
    assert (await client.post(f"/api/v1/lms/bookmarks/me/{other_lesson.id}", headers=headers)).status_code == 403


async def test_a_finished_course_can_still_be_bookmarked_and_listed(client, db_session, organization):
    student, headers = await _create_student_with_login(client, db_session, organization)
    course, lesson = await _create_lesson(db_session, organization, student)
    enrolment = await EnrollmentRepository(db_session).get_by_student_and_course(student.id, course.id)
    await EnrollmentRepository(db_session).set_status(enrolment, EnrollmentStatus.COMPLETED)

    assert (await client.post(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers)).status_code == 201
    assert len((await client.get("/api/v1/lms/bookmarks/me", headers=headers)).json()) == 1


async def test_after_access_is_revoked_the_bookmarks_and_their_titles_disappear_and_return_with_the_enrolment(client, db_session, organization):
    student, headers = await _create_student_with_login(client, db_session, organization)
    course, lesson = await _create_lesson(db_session, organization, student)
    assert (await client.post(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers)).status_code == 201
    listed = (await client.get("/api/v1/lms/bookmarks/me", headers=headers)).json()
    assert [b["lesson_title"] for b in listed] == ["Set Operations"] and listed[0]["course_title"] == "Discrete Math"

    enrolment = await EnrollmentRepository(db_session).get_by_student_and_course(student.id, course.id)
    await EnrollmentRepository(db_session).set_status(enrolment, EnrollmentStatus.DROPPED)
    revoked = await client.get("/api/v1/lms/bookmarks/me", headers=headers)
    assert revoked.status_code == 200 and revoked.json() == []  # no lesson title, no course title
    assert "Set Operations" not in revoked.text and "Discrete Math" not in revoked.text
    # nothing new can be added either (a bookmark that already exists conflicts)
    assert (await client.post(f"/api/v1/lms/bookmarks/me/{lesson.id}", headers=headers)).status_code == 403

    await EnrollmentRepository(db_session).set_status(enrolment, EnrollmentStatus.ACTIVE)  # access given again
    assert [b["lesson_id"] for b in (await client.get("/api/v1/lms/bookmarks/me", headers=headers)).json()] == [str(lesson.id)]
