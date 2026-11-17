"""
LMS access through an internship stays coherent: a dropped enrolment stops opening the course, revoking drops the course the student
was actually given (whatever the internship points at now), a course that students are enrolled in cannot be swapped under them,
only a ready course can be granted, the automatic and manual grants never make two enrolments, and the batch a new student joins is
a sensible one. Synthetic data only.
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select, text

from modules.batches.models import Batch, BatchEnrollment, BatchStatus
from modules.courses.chapters.repository import ChapterRepository
from modules.courses.lessons.repository import LessonRepository
from modules.courses.models import Course, CourseType
from modules.lms.enrollment.models import Enrollment, EnrollmentStatus
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.organizations.repository import OrganizationRepository
from modules.our_internships.models import InternshipSelection, LmsStatus, PaymentStatus, VerificationStatus
from tests.api.test_internship_onboarding import BASE, world
from tests.api.test_lms_transcripts import _create_student_with_login

pytestmark = pytest.mark.api


async def course_in(db, organization, *, published=True, chapters=1, title="Cloud Basics") -> Course:
    course = Course(organization_id=organization.id, title=title, slug=f"c-{uuid.uuid4().hex[:8]}", is_published=published, course_type=CourseType.INTERNSHIP)
    db.add(course)
    await db.flush()
    for i in range(chapters):
        await ChapterRepository(db).create(course_id=course.id, title=f"Chapter {i + 1}", order_index=i + 1)
    await db.flush()
    return course


async def ready(db, internship, student):
    """The student's verification and payment are confirmed, so the only thing left is the grant."""
    selection = (
        await db.execute(select(InternshipSelection).where(InternshipSelection.internship_id == internship.id, InternshipSelection.student_id == student.id))
    ).scalar_one()
    selection.verification_status = VerificationStatus.VERIFIED
    selection.payment_status = PaymentStatus.PAID
    await db.flush()
    return selection


async def grant(client, headers, internship, student):
    return await client.post(f"{BASE}/{internship.id}/selected/{student.id}/lms/grant", headers=headers)


async def revoke(client, headers, internship, student):
    return await client.post(f"{BASE}/{internship.id}/selected/{student.id}/lms/revoke", headers=headers)


async def enrolments(db, course):
    return (await db.execute(select(Enrollment).where(Enrollment.course_id == course.id))).scalars().all()


async def refreshed(db, obj):
    await db.refresh(obj)
    return obj


# ------------------------------------------------------------ a dropped enrolment stops opening the course


async def test_a_dropped_enrolment_no_longer_opens_the_course_but_a_live_or_finished_one_does(client, db_session, organization):
    student, headers = await _create_student_with_login(client, db_session, organization)
    course = await course_in(db_session, organization)
    chapter = (await ChapterRepository(db_session).list_for_course(course.id))[0]
    lesson = await LessonRepository(db_session).create(chapter_id=chapter.id, title="Intro", order_index=1)
    enrolment = await EnrollmentRepository(db_session).create(student_id=student.id, course_id=course.id, enrolled_on=date.today())
    await db_session.flush()
    mine = f"/api/v1/courses/{course.id}"
    doors = [
        ("GET", f"{mine}/me"),
        ("GET", f"{mine}/chapters/me"),
        ("GET", f"{mine}/chapters/{chapter.id}/lessons/me"),
        ("GET", f"/api/v1/lms/progress/me/course/{course.id}"),
        ("POST", f"/api/v1/lms/progress/me/complete/{lesson.id}"),
    ]

    async def statuses():
        return [(await client.request(method, url, headers=headers)).status_code for method, url in doors]

    assert await statuses() == [200, 200, 200, 200, 200]  # enrolled
    await EnrollmentRepository(db_session).set_status(enrolment, EnrollmentStatus.COMPLETED)
    assert await statuses() == [200, 200, 200, 200, 200]  # a finished course can still be read
    await EnrollmentRepository(db_session).set_status(enrolment, EnrollmentStatus.DROPPED)
    assert await statuses() == [403, 403, 403, 403, 403]  # revoked: nothing opens, and no progress can be recorded


async def test_progress_cannot_be_recorded_on_a_course_the_student_is_not_in(client, db_session, organization):
    _, headers = await _create_student_with_login(client, db_session, organization)
    other = await course_in(db_session, organization)
    chapter = (await ChapterRepository(db_session).list_for_course(other.id))[0]
    lesson = await LessonRepository(db_session).create(chapter_id=chapter.id, title="Not mine", order_index=1)
    await db_session.flush()
    assert (await client.post(f"/api/v1/lms/progress/me/complete/{lesson.id}", headers=headers)).status_code == 403
    assert (await client.post(f"/api/v1/lms/progress/me/complete/{uuid.uuid4()}", headers=headers)).status_code == 404


# ------------------------------------------------------------ granting needs a ready course


async def test_only_a_published_course_with_content_can_be_granted_and_the_list_says_why(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, s1) = await world(db_session, organization)
    for s in (s0, s1):
        await ready(db_session, internship, s)
    draft = await course_in(db_session, organization, published=False, title="Draft Course")
    internship.lms_course_id = draft.id
    await db_session.flush()
    listing = (await client.get(f"{BASE}/{internship.id}/selected", headers=auth_headers)).json()["items"]
    assert all('"Draft Course" is not published' in " ".join(row["grant_blockers"]) for row in listing)
    refused = await grant(client, auth_headers, internship, s0)
    assert refused.status_code == 422 and "not published" in refused.json()["error"]["message"]
    bulk = (await client.post(f"{BASE}/{internship.id}/lms/grant", json={"student_ids": [str(s0.id), str(s1.id)]}, headers=auth_headers)).json()
    assert bulk["granted"] == 0 and all(not r["ok"] and "not published" in r["message"] for r in bulk["results"])

    empty = await course_in(db_session, organization, chapters=0, title="Empty Course")
    internship.lms_course_id = empty.id
    await db_session.flush()
    no_content = await grant(client, auth_headers, internship, s0)
    assert no_content.status_code == 422 and "no chapters" in no_content.json()["error"]["message"]
    assert await enrolments(db_session, draft) == [] and await enrolments(db_session, empty) == []  # nothing half-created

    good = await course_in(db_session, organization, title="Good Course")
    internship.lms_course_id = good.id
    await db_session.flush()
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    assert len(await enrolments(db_session, good)) == 1


async def test_the_automatic_grant_waits_for_a_ready_course_and_then_enrols_once(client, auth_headers, db_session, organization, rbac_seeded):
    from modules.internship_onboarding.completion import follow_up
    from modules.internship_onboarding.models import OnboardingApplication, OnboardingEvent
    from tests.api.test_internship_onboarding import configure
    from tests.api.test_internship_onboarding_payments import ready_to_pay

    internship, (s0, _) = await world(db_session, organization)
    await configure(client, auth_headers, internship, modes={"require_payment": False, "lms_access": "automatic"}, fees={"base_amount": "0", "methods": [], "late_fee": {"mode": "none", "value": "0"}})
    await ready_to_pay(client, auth_headers, internship, s0)
    from modules.internship_onboarding.models import OnboardingDocument

    application = (await db_session.execute(select(OnboardingApplication))).scalar_one()
    for d in (await db_session.execute(select(OnboardingDocument))).scalars().all():
        await client.post(f"{BASE}/{internship.id}/onboarding-flow/documents/{d.id}/review", json={"approve": True}, headers=auth_headers)
    await db_session.refresh(application)
    assert application.completed_at is not None

    draft = await course_in(db_session, organization, published=False, title="Not Yet")
    internship.lms_course_id = draft.id
    await db_session.flush()
    assert await follow_up(db_session, application.id) == "blocked"
    waiting = (await db_session.execute(select(OnboardingEvent.detail).where(OnboardingEvent.application_id == application.id, OnboardingEvent.event == "lms_waiting"))).scalars().all()
    assert waiting and "not published" in waiting[-1]["reason"]
    assert await enrolments(db_session, draft) == []

    draft.is_published = True
    await ChapterRepository(db_session).create(course_id=draft.id, title="Second", order_index=2)
    await db_session.flush()
    assert await follow_up(db_session, application.id) == "granted"
    assert await follow_up(db_session, application.id) == "already granted"
    assert len(await enrolments(db_session, draft)) == 1
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == s0.id))).scalar_one()
    assert selection.lms_course_id == draft.id


async def test_a_manual_grant_after_the_automatic_one_does_not_make_a_second_enrolment(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    internship.lms_course_id = course.id
    await ready(db_session, internship, s0)
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    again = await grant(client, auth_headers, internship, s0)
    assert again.status_code == 422 and "already" in again.json()["error"]["message"]
    assert len(await enrolments(db_session, course)) == 1
    # revoke, then grant again: the same enrolment comes back to life (never a second row)
    assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.DROPPED]
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.ACTIVE]


# ------------------------------------------------------------ revoking drops the right course only


async def test_revoking_drops_the_course_the_student_was_given_and_nothing_else(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, s1) = await world(db_session, organization)
    original = await course_in(db_session, organization, title="Original")
    replacement = await course_in(db_session, organization, title="Replacement")
    unrelated = await course_in(db_session, organization, title="Unrelated")
    internship.lms_course_id = original.id
    for s in (s0, s1):
        await ready(db_session, internship, s)
        assert (await grant(client, auth_headers, internship, s)).status_code == 200
    # the student also holds an unrelated course
    erpx_student = (await db_session.execute(select(InternshipSelection.lms_student_id).where(InternshipSelection.student_id == s0.id))).scalar_one()
    await EnrollmentRepository(db_session).create(student_id=erpx_student, course_id=unrelated.id, enrolled_on=date.today())
    # the internship is pointed somewhere else behind the screen's back (the screen and API now refuse this; old data could be like it)
    internship.lms_course_id = replacement.id
    await db_session.flush()

    assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
    by_course = {c.title: sorted(e.status.value for e in await enrolments(db_session, c)) for c in (original, replacement, unrelated)}
    assert by_course["Original"] == ["active", "dropped"]  # s0 dropped; s1 untouched (listed in no particular order)
    assert by_course["Replacement"] == []  # never enrolled, never touched
    assert by_course["Unrelated"] == ["active"]  # unrelated access survives


async def test_revoking_keeps_the_course_when_another_internship_also_grants_it(client, auth_headers, db_session, organization, rbac_seeded):
    first, (s0, _) = await world(db_session, organization)
    second, (t0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    first.lms_course_id = second.lms_course_id = course.id
    # the same person is selected on both internships (same email), so they share one account and one enrolment
    t0.email = s0.email
    await db_session.flush()
    for internship, student in ((first, s0), (second, t0)):
        await ready(db_session, internship, student)
        assert (await grant(client, auth_headers, internship, student)).status_code == 200
    assert len(await enrolments(db_session, course)) == 1
    assert (await revoke(client, auth_headers, first, s0)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.ACTIVE]  # still held through the other
    assert (await revoke(client, auth_headers, second, t0)).status_code == 200
    assert [e.status for e in await enrolments(db_session, course)] == [EnrollmentStatus.DROPPED]


# ------------------------------------------------------------ changing the course


async def test_the_course_is_chosen_replaced_with_confirmation_and_never_under_enrolled_students(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, _) = await world(db_session, organization)
    one = await course_in(db_session, organization, title="One")
    two = await course_in(db_session, organization, title="Two")
    url = f"{BASE}/{internship.id}"
    first = await client.patch(url, json={"lms_course_id": str(one.id)}, headers=auth_headers)
    assert first.status_code == 200 and first.json()["lms_course_title"] == "One"  # a first choice needs no confirmation
    same = await client.patch(url, json={"lms_course_id": str(one.id)}, headers=auth_headers)
    assert same.status_code == 200  # choosing the same one again is a no-op
    unconfirmed = await client.patch(url, json={"lms_course_id": str(two.id)}, headers=auth_headers)
    assert unconfirmed.status_code == 409 and unconfirmed.json()["error"]["details"]["code"] == "confirm_replace"
    assert (await client.get(url, headers=auth_headers)).json()["lms_course_id"] == str(one.id)
    replaced = await client.patch(url, json={"lms_course_id": str(two.id), "confirm_replace": True}, headers=auth_headers)
    assert replaced.status_code == 200 and replaced.json()["lms_course_title"] == "Two"

    await ready(db_session, internship, s0)
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    for body in ({"lms_course_id": str(one.id), "confirm_replace": True}, {"lms_course_id": None, "confirm_replace": True}):
        blocked = await client.patch(url, json=body, headers=auth_headers)
        assert blocked.status_code == 409 and blocked.json()["error"]["details"] == {"code": "course_in_use", "enrolled": 1}
        assert "revoke their access first" in blocked.json()["error"]["message"]
    await internship_unchanged(client, auth_headers, internship, two)
    assert [e.status for e in await enrolments(db_session, two)] == [EnrollmentStatus.ACTIVE]  # nobody moved
    assert await enrolments(db_session, one) == []
    # once access is revoked the course can be replaced (still with confirmation)
    assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
    assert (await client.patch(url, json={"lms_course_id": str(one.id), "confirm_replace": True}, headers=auth_headers)).status_code == 200


async def internship_unchanged(client, headers, internship, course):
    got = (await client.get(f"{BASE}/{internship.id}", headers=headers)).json()
    assert got["lms_course_id"] == str(course.id)


async def test_a_course_from_another_organization_cannot_be_linked(client, auth_headers, db_session, organization):
    internship, _ = await world(db_session, organization)
    other_org = await OrganizationRepository(db_session).create(name="Other Org", slug=f"other-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    foreign = await course_in(db_session, other_org, title="Foreign")
    refused = await client.patch(f"{BASE}/{internship.id}", json={"lms_course_id": str(foreign.id)}, headers=auth_headers)
    assert refused.status_code == 404
    assert (await client.get(f"{BASE}/{internship.id}", headers=auth_headers)).json()["lms_course_id"] is None


async def test_only_an_internship_administrator_may_choose_the_course_not_an_assigned_instructor(client, auth_headers, db_session, organization):
    from tests.api.test_internship_instructors import _assign, _instructor
    from tests.api.test_internship_learning import _world

    internship, _ = await _world(client, auth_headers, db_session, organization)
    trainer, instructor_headers = await _instructor(client, db_session, organization)
    await _assign(client, auth_headers, internship, trainer)
    course = await course_in(db_session, organization)
    url = f"{BASE}/{internship['id']}"
    refused = await client.patch(url, json={"lms_course_id": str(course.id)}, headers=instructor_headers)
    assert refused.status_code == 403 and "administrator" in refused.json()["error"]["message"]
    # what the instructor may do on the internship is unchanged
    assert (await client.patch(url, json={"description": "Updated by the instructor"}, headers=instructor_headers)).status_code == 200
    assert (await client.patch(url, json={"lms_course_id": str(course.id)}, headers=auth_headers)).status_code == 200


# ------------------------------------------------------------ the batch a new student joins


async def test_a_new_student_joins_the_soonest_upcoming_batch_never_a_finished_or_cancelled_one(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, s1) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    internship.lms_course_id = course.id
    today = date.today()

    def batch(name, status, start, end=None):
        b = Batch(organization_id=organization.id, course_id=course.id, name=name, code=f"B-{uuid.uuid4().hex[:6]}", status=status, start_date=start, end_date=end)
        db_session.add(b)
        return b

    finished = batch("Finished (latest start)", BatchStatus.COMPLETED, today + timedelta(days=90), today + timedelta(days=100))
    cancelled = batch("Cancelled", BatchStatus.CANCELLED, today + timedelta(days=80))
    soon = batch("Soon", BatchStatus.UPCOMING, today + timedelta(days=10))
    later = batch("Later", BatchStatus.UPCOMING, today + timedelta(days=40))
    ongoing = batch("Ongoing", BatchStatus.ONGOING, today - timedelta(days=20), today + timedelta(days=30))
    await db_session.flush()
    await ready(db_session, internship, s0)
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200

    async def joined():
        rows = await db_session.execute(select(BatchEnrollment.batch_id))
        return set(rows.scalars().all())

    assert await joined() == {soon.id}
    # with no upcoming batch the student joins the one that is running; finished and cancelled ones are still never used
    for b in (soon, later):
        b.status = BatchStatus.COMPLETED
    await db_session.flush()
    await db_session.execute(text("DELETE FROM batch_enrollments"))
    await ready(db_session, internship, s1)
    assert (await grant(client, auth_headers, internship, s1)).status_code == 200
    assert await joined() == {ongoing.id}
    assert finished.id not in await joined() and cancelled.id not in await joined()


# ------------------------------------------------------------ the migration's backfill


async def test_the_backfill_records_the_course_only_for_students_who_have_or_had_access(db_session, organization):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "apps/api/alembic/versions/0104_internship_lms_course_on_selection.py"
    spec = importlib.util.spec_from_file_location("m0104", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sql = module.BACKFILL_SQL

    internship, (granted, revoked, never) = await world(db_session, organization, n=3)
    course = await course_in(db_session, organization)
    internship.lms_course_id = course.id
    sel = {}
    for name, student, status in (("granted", granted, LmsStatus.GRANTED), ("revoked", revoked, LmsStatus.REVOKED), ("never", never, LmsStatus.NOT_GRANTED)):
        s = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == student.id))).scalar_one()
        s.lms_status = status
        sel[name] = s
    await db_session.flush()
    await db_session.execute(text(sql))
    await db_session.execute(text(sql))  # safe to run twice
    for s in sel.values():
        await db_session.refresh(s)
    assert (sel["granted"].lms_course_id, sel["revoked"].lms_course_id, sel["never"].lms_course_id) == (course.id, course.id, None)
    assert (await db_session.execute(select(func.count()).select_from(Enrollment))).scalar_one() == 0  # nothing enrolled by the backfill


# ------------------------------------------------------------ batches, timetable and live classes follow the enrolment


async def test_revoking_removes_the_batches_of_that_course_only_and_granting_again_restores_them(client, auth_headers, db_session, organization, rbac_seeded):
    internship, (s0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization, title="Internship Course")
    elsewhere = await course_in(db_session, organization, title="Another Course")
    internship.lms_course_id = course.id
    today = date.today()
    mine = Batch(organization_id=organization.id, course_id=course.id, name="Cohort", code=f"B-{uuid.uuid4().hex[:6]}", status=BatchStatus.UPCOMING, start_date=today + timedelta(days=5))
    other = Batch(organization_id=organization.id, course_id=elsewhere.id, name="Other cohort", code=f"B-{uuid.uuid4().hex[:6]}", status=BatchStatus.ONGOING, start_date=today)
    db_session.add_all([mine, other])
    await db_session.flush()
    await ready(db_session, internship, s0)
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    erpx_student = (await db_session.execute(select(InternshipSelection.lms_student_id).where(InternshipSelection.student_id == s0.id))).scalar_one()
    db_session.add(BatchEnrollment(organization_id=organization.id, batch_id=other.id, student_id=erpx_student, enrolled_at=today))  # an unrelated batch
    await db_session.flush()

    async def states():
        rows = (await db_session.execute(select(BatchEnrollment.batch_id, BatchEnrollment.status))).all()
        return {batch_id: status.value for batch_id, status in rows}

    assert await states() == {mine.id: "active", other.id: "active"}
    assert (await revoke(client, auth_headers, internship, s0)).status_code == 200
    assert await states() == {mine.id: "removed", other.id: "active"}  # live classes of this course stop; the other course is untouched
    assert (await grant(client, auth_headers, internship, s0)).status_code == 200
    assert await states() == {mine.id: "active", other.id: "active"}


# ------------------------------------------------------------ two grants for the same person arriving together


async def test_a_grant_that_loses_the_race_for_the_same_enrolment_finds_it_instead_of_failing(client, auth_headers, db_session, organization, rbac_seeded, monkeypatch):
    first, (s0, _) = await world(db_session, organization)
    second, (t0, _) = await world(db_session, organization)
    course = await course_in(db_session, organization)
    first.lms_course_id = second.lms_course_id = course.id
    t0.email = s0.email
    await db_session.flush()
    await ready(db_session, first, s0)
    assert (await grant(client, auth_headers, first, s0)).status_code == 200  # the winner made the enrolment
    await ready(db_session, second, t0)

    real = EnrollmentRepository.get_by_student_and_course
    calls = {"n": 0}

    async def stale_first_look(self, student_id, course_id):
        calls["n"] += 1
        return None if calls["n"] == 1 else await real(self, student_id, course_id)  # the loser looked before the winner's row was visible

    monkeypatch.setattr(EnrollmentRepository, "get_by_student_and_course", stale_first_look)
    assert (await grant(client, auth_headers, second, t0)).status_code == 200  # no error, no second row
    monkeypatch.undo()
    assert len(await enrolments(db_session, course)) == 1
    assert {s.lms_status for s in (await db_session.execute(select(InternshipSelection).where(InternshipSelection.lms_course_id == course.id))).scalars()} == {LmsStatus.GRANTED}
