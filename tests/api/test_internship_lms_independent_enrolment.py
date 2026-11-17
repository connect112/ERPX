"""
Withdrawing LMS access through an internship must not take away an enrolment the student had anyway.

The failure this guards against: a student is enrolled in a course by an administrator (or bought it), an internship that uses the same
course then grants them LMS access (the enrolment already exists, so nothing is created), and revoking that internship's access used to
drop the enrolment, which belonged to the student independently of the internship (and the batches that came with it). The grant now
remembers whether it created or restored the enrolment (``lms_enrolment_preexisting``); only an enrolment the grant made is withdrawn.
Synthetic data only.
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from modules.authentication.models import User
from modules.batches.models import Batch, BatchEnrollment, BatchStatus
from modules.lms.enrollment.models import Enrollment, EnrollmentStatus
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.our_internships.models import InternshipSelection, LmsStatus
from tests.api.test_internship_lms_integrity import course_in, enrolments, grant, ready, revoke
from tests.api.test_internship_onboarding import world
from tests.api.test_lms_transcripts import _create_student_with_login

pytestmark = pytest.mark.api


async def independent_student(client, db, organization, internship_student, course, status=EnrollmentStatus.ACTIVE):
    """A student of the organization who already has an enrolment in the course (not through any internship), whose account the
    internship student's email points at, so a grant finds that account instead of making a new one."""
    student, headers = await _create_student_with_login(client, db, organization)
    user = (await db.execute(select(User).where(User.id == student.user_id))).scalar_one()
    internship_student.email = user.email
    enrolment = await EnrollmentRepository(db).create(student_id=student.id, course_id=course.id, enrolled_on=date.today() - timedelta(days=30))
    if status != EnrollmentStatus.ACTIVE:
        await EnrollmentRepository(db).set_status(enrolment, status)
    await db.flush()
    return student, headers, enrolment


async def selection_of(db, internship, internship_student):
    row = (await db.execute(select(InternshipSelection).where(InternshipSelection.internship_id == internship.id, InternshipSelection.student_id == internship_student.id))).scalar_one()
    await db.refresh(row)
    return row


async def opens(client, headers, course):
    return (await client.get(f"/api/v1/courses/{course.id}/chapters/me", headers=headers)).status_code


async def test_revoking_leaves_an_enrolment_the_student_already_had_and_its_batches(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    internship.lms_course_id = course.id
    student, headers, _ = await independent_student(client, db_session, organization, s0, course)
    cohort = Batch(organization_id=organization.id, course_id=course.id, name="Cohort", code=f"B-{uuid.uuid4().hex[:6]}", status=BatchStatus.ONGOING, start_date=date.today())
    db_session.add(cohort)
    await db_session.flush()
    db_session.add(BatchEnrollment(organization_id=organization.id, batch_id=cohort.id, student_id=student.id, enrolled_at=date.today()))
    await db_session.flush()
    await ready(db_session, internship, s0)

    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    assert len(await enrolments(db_session, course)) == 1  # the grant found the student's own enrolment, it made no second one
    assert (await selection_of(db_session, internship, s0)).lms_enrolment_preexisting is True

    assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
    assert (await selection_of(db_session, internship, s0)).lms_status == LmsStatus.REVOKED  # the internship's access is withdrawn
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.ACTIVE]  # the student's own enrolment is not
    assert await opens(client, headers, course) == 200
    states = (await db_session.execute(select(BatchEnrollment.status))).scalars().all()
    assert [s.value for s in states] == ["active"]  # and neither is their place in the course's batch


async def test_a_finished_independent_enrolment_stays_finished(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    internship.lms_course_id = course.id
    _, headers, _ = await independent_student(client, db_session, organization, s0, course, status=EnrollmentStatus.COMPLETED)
    await ready(db_session, internship, s0)
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.COMPLETED]
    assert await opens(client, headers, course) == 200


async def test_an_enrolment_the_student_had_dropped_is_restored_by_the_grant_and_dropped_again_by_the_revoke(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    internship.lms_course_id = course.id
    _, headers, _ = await independent_student(client, db_session, organization, s0, course, status=EnrollmentStatus.DROPPED)
    await ready(db_session, internship, s0)
    assert await opens(client, headers, course) == 403
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    assert (await selection_of(db_session, internship, s0)).lms_enrolment_preexisting is False  # this grant brought it back, so it is this grant's
    assert await opens(client, headers, course) == 200
    assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.DROPPED]  # back to how it was
    assert await opens(client, headers, course) == 403


async def test_an_enrolment_the_internship_created_is_still_withdrawn_every_time_and_a_regrant_recomputes_it(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    internship.lms_course_id = course.id
    await ready(db_session, internship, s0)
    for _round in range(2):
        assert (await grant(client, auth_headers, internship, s0)).status_code == 200
        assert (await selection_of(db_session, internship, s0)).lms_enrolment_preexisting is False
        assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.ACTIVE]
        assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
        assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.DROPPED]


async def test_a_grant_after_a_kept_revoke_still_knows_the_enrolment_was_never_its_own(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    internship.lms_course_id = course.id
    _, headers, _ = await independent_student(client, db_session, organization, s0, course)
    await ready(db_session, internship, s0)
    for _round in range(2):
        assert (await grant(client, auth_headers, internship, s0)).status_code == 200
        assert (await selection_of(db_session, internship, s0)).lms_enrolment_preexisting is True
        assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
        assert await opens(client, headers, course) == 200


async def test_with_two_internships_the_one_that_made_the_enrolment_hands_it_over_when_withdrawn_first(client, auth_headers, db_session, organization, rbac_seeded):
    first, (s0, _) = await world(db_session, organization)
    second, (t0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    first.lms_course_id = second.lms_course_id = course.id
    t0.email = s0.email
    await db_session.flush()
    for internship, student in ((first, s0), (second, t0)):
        await ready(db_session, internship, student)
        assert (await grant(client, auth_headers, internship, student)).status_code == 200
    assert (await selection_of(db_session, first, s0)).lms_enrolment_preexisting is False  # made it
    assert (await selection_of(db_session, second, t0)).lms_enrolment_preexisting is True  # found it

    assert (await revoke(client, auth_headers, first, s0)).status_code == 200  # the maker leaves first: the other still needs it
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.ACTIVE]
    assert (await selection_of(db_session, second, t0)).lms_enrolment_preexisting is False  # so it now owns it
    assert (await revoke(client, auth_headers, second, t0)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.DROPPED]  # nobody relies on it any more


async def test_with_two_internships_the_one_that_only_found_it_can_leave_first(client, auth_headers, db_session, organization, rbac_seeded):
    first, (s0, _) = await world(db_session, organization)
    second, (t0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    first.lms_course_id = second.lms_course_id = course.id
    t0.email = s0.email
    await db_session.flush()
    for internship, student in ((first, s0), (second, t0)):
        await ready(db_session, internship, student)
        assert (await grant(client, auth_headers, internship, student)).status_code == 200
    assert (await revoke(client, auth_headers, second, t0)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.ACTIVE]  # the maker still holds it
    assert (await revoke(client, auth_headers, first, s0)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.DROPPED]


async def test_an_independent_enrolment_survives_the_withdrawal_of_every_internship_that_uses_the_course(client, auth_headers, db_session, organization, rbac_seeded):
    first, (s0, _) = await world(db_session, organization)
    second, (t0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    first.lms_course_id = second.lms_course_id = course.id
    _, headers, _ = await independent_student(client, db_session, organization, s0, course)
    t0.email = s0.email
    await db_session.flush()
    for internship, student in ((first, s0), (second, t0)):
        await ready(db_session, internship, student)
        assert (await grant(client, auth_headers, internship, student)).status_code == 200
    for internship, student in ((first, s0), (second, t0)):
        assert (await revoke(client, auth_headers, internship, student)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.ACTIVE]
    assert await opens(client, headers, course) == 200


async def test_access_granted_before_the_column_existed_behaves_as_it_always_did(client, auth_headers, db_session, organization, rbac_seeded):
    """Every selection that already existed when the column was added is false: revoking drops the enrolment, exactly as before. (Nothing
    is guessed about whether an older enrolment was independent; ops/preflight/0104_0106_lms_access_ambiguity.sql lists candidates.)"""
    internship, (s0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    internship.lms_course_id = course.id
    student, headers, _ = await independent_student(client, db_session, organization, s0, course)
    await ready(db_session, internship, s0)
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    (await selection_of(db_session, internship, s0)).lms_enrolment_preexisting = False  # as a row from before the column would be
    await db_session.flush()
    assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.DROPPED]
