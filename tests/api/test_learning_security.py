"""
Identity and ownership on the course learning routes: a student always acts as themselves (a client-supplied student id or score never
decides who or what is recorded), an attempt belongs to its student, staff act for a named student only inside their own organization, and
the student guard on the examination routes needs a live enrolment. Synthetic data only.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from modules.lms.enrollment.models import Enrollment, EnrollmentStatus
from modules.organizations.repository import OrganizationRepository
from tests.api.test_internship_learning import _world
from tests.api.test_learning_integration import _LMS, _link, _roles, _solo  # noqa: F401  (the autouse role fixture applies here too)
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_EX = "/api/v1/examinations"


async def _exam(client, headers, course):
    r = await client.post(f"{_EX}/courses/{course.id}/exams", json={"title": "Midterm", "exam_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), "duration_minutes": 30, "passing_marks": 10}, headers=headers)
    assert r.status_code == 201, r.text
    opened = await client.patch(f"{_EX}/courses/{course.id}/exams/{r.json()['id']}", json={"status": "scheduled"}, headers=headers)
    assert opened.status_code == 200, opened.text
    return r.json()


async def _start(client, headers, exam, student_id=None):
    return await client.post(f"{_EX}/exams/{exam['id']}/attempts", json={"student_id": student_id} if student_id else {}, headers=headers)


# ------------------------------------------------------------ an examination attempt belongs to its student


async def test_a_student_cannot_read_answer_or_submit_another_students_attempt(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    exam = await _exam(client, auth_headers, course)
    asha, meera = people["asha@example.com"][1], people["meera@example.com"][1]
    started = await _start(client, asha, exam)
    assert started.status_code == 201, started.text
    attempt = started.json()["id"]
    base = f"{_EX}/attempts/{attempt}"
    assert (await client.post(f"{base}/answers", json={"question_id": str(uuid.uuid4()), "answer_text": "x"}, headers=meera)).status_code == 403
    assert (await client.post(f"{base}/submit", headers=meera)).status_code == 403
    assert (await client.post(f"{base}/submit", headers=asha)).status_code == 200  # the owner still can
    assert (await client.get(f"{base}/answers", headers=auth_headers)).status_code == 200  # and so can staff


async def test_a_student_cannot_start_an_attempt_for_someone_else(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    exam = await _exam(client, auth_headers, course)
    from modules.students.repository import StudentRepository
    from modules.our_internships.models import InternshipSelection

    meera_row = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(people["meera@example.com"][0])))).scalar_one()
    forged = await _start(client, people["asha@example.com"][1], exam, student_id=str(meera_row.lms_student_id))
    assert forged.status_code == 403
    assert (await db_session.execute(select(Enrollment))).scalars().all()  # (the enrolments are untouched)
    # naming themselves is fine, and so is staff recording for a named student
    assert (await _start(client, people["asha@example.com"][1], exam)).status_code == 201
    assert (await _start(client, auth_headers, exam, student_id=str(meera_row.lms_student_id))).status_code == 201


async def test_staff_cannot_act_for_a_student_of_another_organization(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    exam = await _exam(client, auth_headers, course)
    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    from modules.students.models import Student

    stranger = Student(organization_id=other_org.id, student_code=f"S-{uuid.uuid4().hex[:8]}", full_name="Elsewhere", email="else@example.com", course_name="Cyber", enrollment_date=date(2026, 1, 1))
    db_session.add(stranger)
    await db_session.flush()
    assert (await _start(client, auth_headers, exam, student_id=str(stranger.id))).status_code == 404


async def test_an_exam_of_another_organization_is_not_found(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    exam = await _exam(client, auth_headers, course)
    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"x-{uuid.uuid4().hex[:6]}@other.example.com")
    outsider = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{_EX}/courses/{course.id}/exams/{exam['id']}", headers=outsider)).status_code == 404


async def test_the_student_guard_closes_the_examination_routes_once_the_enrolment_is_dropped(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    asha = people["asha@example.com"][1]
    assert (await client.get(f"{_EX}/courses/{course.id}/practicals/me", headers=asha)).status_code == 200
    enrolments = (await db_session.execute(select(Enrollment).where(Enrollment.course_id == course.id))).scalars().all()
    for e in enrolments:
        e.status = EnrollmentStatus.DROPPED
    await db_session.flush()
    for kind in ("practicals", "viva", "exams"):
        gone = await client.get(f"{_EX}/courses/{course.id}/{kind}/me" if kind != "exams" else f"{_EX}/courses/{course.id}/exams", headers=asha)
        assert gone.status_code in (403, 404), (kind, gone.status_code)


# ------------------------------------------------------------ who a request is for (assignments and attempts share one rule)


async def test_a_student_linked_caller_is_always_themselves_and_staff_must_name_a_student_of_their_own_organization(client, auth_headers, db_session, organization):
    from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
    from modules.authentication.models import User
    from modules.our_internships.models import InternshipSelection
    from modules.students.actor import ensure_own_or_staff, resolve_actor

    internship, people = await _world(client, auth_headers, db_session, organization)
    await _link(db_session, organization, internship)
    rows = {e: (await db_session.execute(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(people[e][0])))).scalar_one() for e in ("asha@example.com", "meera@example.com")}
    from modules.students.models import Student

    asha = (await db_session.execute(select(Student).where(Student.id == rows["asha@example.com"].lms_student_id))).scalar_one()
    meera = (await db_session.execute(select(Student).where(Student.id == rows["meera@example.com"].lms_student_id))).scalar_one()
    asha_user = (await db_session.execute(select(User).where(User.id == asha.user_id))).scalar_one()
    STAFF = {"lms.assignments.manage"}

    assert (await resolve_actor(db_session, asha_user, organization.id, None, STAFF)).id == asha.id  # no id needed
    assert (await resolve_actor(db_session, asha_user, organization.id, asha.id, STAFF)).id == asha.id  # their own id is fine
    with pytest.raises(AuthorizationError):
        await resolve_actor(db_session, asha_user, organization.id, meera.id, STAFF)  # someone else's is refused
    with pytest.raises(AuthorizationError):
        await ensure_own_or_staff(db_session, asha_user, meera.id, STAFF)  # and so is touching their attempt
    await ensure_own_or_staff(db_session, asha_user, asha.id, STAFF)

    admin_user = (await db_session.execute(select(User).where(User.is_superuser.is_(True), User.id != asha_user.id))).scalars().first()
    if admin_user is None:  # the autouse admin is created with the auth_headers fixture
        pytest.fail("no staff user to test with")
    with pytest.raises(ValidationError):
        await resolve_actor(db_session, admin_user, organization.id, None, STAFF)  # staff must say who
    assert (await resolve_actor(db_session, admin_user, organization.id, meera.id, STAFF)).id == meera.id
    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    with pytest.raises(NotFoundError):
        await resolve_actor(db_session, admin_user, other_org.id, meera.id, STAFF)  # not their organization's student
