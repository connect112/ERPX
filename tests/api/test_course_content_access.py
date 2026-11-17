"""
A student reads a course's content (chapters, lessons, lesson resources, assessments, assignments, discussions) only while their
enrolment in that course is live. The Student role holds the *view* permissions for all of these, so the routes themselves cannot tell
an enrolled student from one who was never enrolled or whose access was revoked: the course guard does. Staff, trainers and course
authors are decided by their own permissions, as before. Synthetic data only.
"""

import uuid
from datetime import date

import pytest

from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.courses.chapters.repository import ChapterRepository
from modules.courses.lessons.repository import LessonRepository
from modules.courses.models import Course
from modules.lms.enrollment.models import EnrollmentStatus
from modules.lms.enrollment.repository import EnrollmentRepository
from tests.api.test_email_studio import user_with
from tests.api.test_lms_transcripts import _create_student_with_login

pytestmark = pytest.mark.api


async def student_with_role(client, db, organization):
    student, headers = await _create_student_with_login(client, db, organization)
    role = await AuthorizationRepository(db).get_role_by_slug("student")
    await AuthorizationService(db).assign_role(student.user_id, role.id, organization.id, assigned_by_user_id=None)
    await db.flush()
    return student, headers


async def a_course(db, organization):
    course = Course(organization_id=organization.id, title="Content Course", slug=f"cc-{uuid.uuid4().hex[:8]}", is_published=True)
    db.add(course)
    await db.flush()
    chapter = await ChapterRepository(db).create(course_id=course.id, title="Chapter", order_index=1)
    lesson = await LessonRepository(db).create(chapter_id=chapter.id, title="Lesson", order_index=1)
    await db.flush()
    return course, chapter, lesson


def doors(course, chapter, lesson):
    c = f"/api/v1/courses/{course.id}"
    lms = f"/api/v1/lms/courses/{course.id}"
    return [
        ("GET", f"{c}/chapters"),
        ("GET", f"{c}/chapters/{chapter.id}"),
        ("GET", f"{c}/chapters/{chapter.id}/lessons"),
        ("GET", f"{c}/chapters/{chapter.id}/lessons/{lesson.id}"),
        ("GET", f"{c}/chapters/{chapter.id}/lessons/{lesson.id}/resources"),
        ("GET", f"{lms}/assessments"),
        ("GET", f"{lms}/assignments"),
        ("GET", f"{lms}/discussions"),
    ]


async def codes(client, headers, door_list):
    return [(await client.request(method, url, headers=headers)).status_code for method, url in door_list]


async def test_content_opens_only_through_a_live_enrolment(client, db_session, organization, rbac_seeded):
    student, headers = await student_with_role(client, db_session, organization)
    course, chapter, lesson = await a_course(db_session, organization)
    door_list = doors(course, chapter, lesson)

    assert set(await codes(client, headers, door_list)) == {403}  # never enrolled: nothing opens
    enrolment = await EnrollmentRepository(db_session).create(student_id=student.id, course_id=course.id, enrolled_on=date.today())
    await db_session.flush()
    assert set(await codes(client, headers, door_list)) == {200}  # enrolled
    await EnrollmentRepository(db_session).set_status(enrolment, EnrollmentStatus.COMPLETED)
    assert set(await codes(client, headers, door_list)) == {200}  # finished: still readable
    await EnrollmentRepository(db_session).set_status(enrolment, EnrollmentStatus.DROPPED)
    assert set(await codes(client, headers, door_list)) == {403}  # revoked: shut again, on every route


async def test_enrolment_in_one_course_opens_nothing_in_another(client, db_session, organization, rbac_seeded):
    student, headers = await student_with_role(client, db_session, organization)
    mine = await a_course(db_session, organization)
    other = await a_course(db_session, organization)
    await EnrollmentRepository(db_session).create(student_id=student.id, course_id=mine[0].id, enrolled_on=date.today())
    await db_session.flush()
    assert set(await codes(client, headers, doors(*mine))) == {200}
    assert set(await codes(client, headers, doors(*other))) == {403}


async def test_writes_are_shut_too_and_the_guard_runs_before_the_request_is_read(client, db_session, organization, rbac_seeded):
    student, headers = await student_with_role(client, db_session, organization)
    course, chapter, lesson = await a_course(db_session, organization)
    lms = f"/api/v1/lms/courses/{course.id}"
    for url in (f"{lms}/discussions", f"{lms}/assessments/{uuid.uuid4()}/attempts", f"{lms}/assignments/{uuid.uuid4()}/submissions"):
        r = await client.post(url, json={}, headers=headers)
        assert r.status_code == 403, (url, r.status_code)


async def test_staff_trainers_and_authors_are_not_held_to_enrolment(client, db_session, organization, auth_headers, rbac_seeded):
    course, chapter, lesson = await a_course(db_session, organization)
    door_list = doors(course, chapter, lesson)
    assert set(await codes(client, auth_headers, door_list)) == {200}  # a superuser
    viewer = await user_with(db_session, organization, ["courses.view", "lms.assessments.view", "lms.assignments.view", "lms.discussions.participate"])
    assert set(await codes(client, viewer, door_list)) == {200}  # a staff member who is not a student
    # even someone with a student record who also authors courses keeps their authoring access
    student, headers = await student_with_role(client, db_session, organization)
    authoring = await AuthorizationRepository(db_session).create_role(f"Authors {uuid.uuid4().hex[:6]}", f"authors-{uuid.uuid4().hex[:6]}", "test")
    await db_session.flush()
    perms = [await AuthorizationRepository(db_session).get_or_create_permission("courses.manage", "courses", "courses.manage")]
    await AuthorizationRepository(db_session).set_role_permissions(authoring, perms)
    await AuthorizationService(db_session).assign_role(student.user_id, authoring.id, organization.id, assigned_by_user_id=None)
    await db_session.flush()
    assert (await client.get(f"/api/v1/courses/{course.id}/chapters", headers=headers)).status_code == 200


async def test_the_course_catalog_itself_stays_browsable(client, db_session, organization, rbac_seeded):
    _, headers = await student_with_role(client, db_session, organization)
    course, _, _ = await a_course(db_session, organization)
    assert (await client.get("/api/v1/courses/", headers=headers)).status_code == 200  # listing and detail are catalog metadata
    assert (await client.get(f"/api/v1/courses/{course.id}", headers=headers)).status_code == 200
