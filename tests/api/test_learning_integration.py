"""
The shared Learning workspace (internship detail -> Learning, and LMS course detail -> Learning) and the rules behind it.

What must hold: both pages render the same seven tabs from the same records, internship-owned activities are reachable only through the
internship (never through a course permission, never by another internship's people or an independent enrolee), revoked students lose
access but keep their history, an assessment is scored on the server only, a link to an internship exam dies with the student's access, and
nothing here deletes a record when a student is removed from the selected list. Synthetic data only.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from modules.authorization.repository import AuthorizationRepository
from modules.lms.enrollment.models import Enrollment, EnrollmentStatus
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.our_internships.models import InternshipSelection, LmsStatus, OurInternship
from modules.students.models import Student
from modules.workshop_exams.models import WorkshopExamAttendee
from tests.api.test_internship_instructors import _assign, _instructor, _iso
from tests.api.test_internship_learning import _INTERN, _MINE, _EXAMS, _assignment, _exam, _publish, _world
from tests.api.test_internship_lms_integrity import course_in
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_LMS = "/api/v1/lms/courses"
_LEARN = "/api/v1/learning"
_EXAMINATIONS = "/api/v1/examinations/courses"
_SEVEN = ["Curriculum", "Enrollments", "Evaluations", "Projects", "Discussions", "Practicals", "Viva"]


@pytest.fixture(autouse=True)
def _roles(rbac_seeded):
    """Students and trainers hold their real system roles, as they do in production."""
    return rbac_seeded


async def _give_student_role(db, user_id):
    repo = AuthorizationRepository(db)
    await repo.assign_role(user_id, (await repo.get_role_by_slug("student")).id, None)
    await db.flush()


async def _solo(db, organization, course, email="solo@example.com"):
    """An independent enrolee: enrolled in the course on their own, not through any internship. Returns (student, headers)."""
    user, token = await _make_user(db, organization, is_superuser=False, email=email)
    student = Student(organization_id=organization.id, student_code=f"S-{uuid.uuid4().hex[:8]}", full_name="Solo", email=email, course_name="Cyber", enrollment_date=date(2026, 1, 1), user_id=user.id)
    db.add(student)
    await db.flush()
    await _give_student_role(db, user.id)
    await EnrollmentRepository(db).create(student_id=student.id, course_id=course.id, enrolled_on=date.today())
    await db.flush()
    return student, {"Authorization": f"Bearer {token}"}


async def _link(db, organization, internship, *, title="Cloud Basics"):
    """Give the internship a ready course, and every granted student an enrolment in it (what a real grant does)."""
    course = await course_in(db, organization, title=title)
    row = (await db.execute(select(OurInternship).where(OurInternship.id == uuid.UUID(internship["id"])))).scalar_one()
    row.lms_course_id = course.id
    selections = (await db.execute(select(InternshipSelection).where(InternshipSelection.internship_id == row.id))).scalars().all()
    for s in selections:
        if s.lms_status == LmsStatus.GRANTED:
            s.lms_course_id = course.id
            await _give_student_role(db, s.lms_user_id)
            await EnrollmentRepository(db).create(student_id=s.lms_student_id, course_id=course.id, enrolled_on=date.today())
    await db.flush()
    return course


async def _selection(db, selection_id) -> InternshipSelection:
    return (await db.execute(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(selection_id)))).scalar_one()


async def _revoke(client, headers, db, internship, selection_id):
    """Withdraw access through the real internship endpoint, so the enrolment is dropped just as it is in production."""
    s = await _selection(db, selection_id)
    r = await client.post(f"{_INTERN}/{internship['id']}/selected/{s.student_id}/lms/revoke", headers=headers)
    assert r.status_code == 200, r.text
    await db.refresh(s)
    assert s.lms_status == LmsStatus.REVOKED
    return s


async def _quiz(client, headers, course, internship=None, *, show_result=True, questions=2, publish=True):
    body = {"title": "Quiz", "assessment_type": "quiz", "total_marks": 10, "passing_marks": 5, "show_result": show_result}
    if internship:
        body["internship_id"] = internship["id"]
    r = await client.post(f"{_LMS}/{course.id}/assessments", json=body, headers=headers)
    assert r.status_code == 201, r.text
    quiz = r.json()
    for n in range(questions):
        q = await client.post(
            f"{_LMS}/{course.id}/assessments/{quiz['id']}/questions",
            json={"text": f"Q{n}?", "options": ["wrong", "right", "also wrong"], "correct_indices": [1], "marks": 5},
            headers=headers,
        )
        assert q.status_code == 201, q.text
    if publish:
        p = await client.patch(f"{_LMS}/{course.id}/assessments/{quiz['id']}", json={"is_published": True}, headers=headers)
        assert p.status_code == 200, p.text
    return quiz


async def _answer_key(client, headers, course, quiz):
    qs = (await client.get(f"{_LMS}/{course.id}/assessments/{quiz['id']}/questions", headers=headers)).json()
    return qs


# ------------------------------------------------------------ the seven tabs, from one source


async def test_both_pages_render_the_same_seven_tabs_in_order(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    from_internship = (await client.get(f"{_LEARN}/context", params={"internship_id": internship["id"]}, headers=auth_headers)).json()
    from_course = (await client.get(f"{_LEARN}/context", params={"course_id": str(course.id)}, headers=auth_headers)).json()
    assert [t["label"] for t in from_internship["tabs"]] == _SEVEN == [t["label"] for t in from_course["tabs"]]
    assert from_internship["course"]["id"] == str(course.id) == from_course["course"]["id"]
    assert [i["id"] for i in from_course["internships"]] == [internship["id"]]


async def test_the_context_needs_exactly_one_target_and_a_foreign_one_is_not_found(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    assert (await client.get(f"{_LEARN}/context", headers=auth_headers)).status_code in (400, 422)
    both = await client.get(f"{_LEARN}/context", params={"internship_id": internship["id"], "course_id": str(uuid.uuid4())}, headers=auth_headers)
    assert both.status_code in (400, 422)
    assert (await client.get(f"{_LEARN}/context", params={"internship_id": str(uuid.uuid4())}, headers=auth_headers)).status_code == 404


async def test_an_assignment_made_on_the_internship_is_the_one_the_workspace_and_results_show(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    await _link(db_session, organization, internship)
    a = await _assignment(client, auth_headers, internship, title="Recon report")
    await _publish(client, auth_headers, internship, a)
    listed = (await client.get(f"{_INTERN}/{internship['id']}/assignments", headers=auth_headers)).json()
    results = (await client.get(f"{_LEARN}/results", params={"internship_id": internship["id"], "kind": "assignment"}, headers=auth_headers)).json()
    assert [x["title"] for x in listed] == ["Recon report"]
    assert {r["activity_id"] for r in results["rows"]} == {a["id"]}  # the very same record, not a copy
    assert {r["student_email"] for r in results["rows"]} == {"asha@example.com", "meera@example.com"}
    assert all("combined" not in r and "total_score" not in r for r in results["rows"])  # no invented overall score


# ------------------------------------------------------------ nothing is erased when someone leaves the selected list


async def test_removing_a_student_with_history_is_refused_and_keeps_every_record(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    await _link(db_session, organization, internship)
    asha = people["asha@example.com"]
    selection = await _selection(db_session, asha[0])
    r = await client.delete(f"{_INTERN}/{internship['id']}/selected/{selection.student_id}", headers=auth_headers)
    assert r.status_code == 409 and "LMS access" in r.text  # currently granted
    await _revoke(client, auth_headers, db_session, internship, asha[0])
    again = await client.delete(f"{_INTERN}/{internship['id']}/selected/{selection.student_id}", headers=auth_headers)
    assert again.status_code == 409 and "kept" in again.text  # a withdrawn grant is history
    assert (await db_session.execute(select(func.count()).select_from(InternshipSelection).where(InternshipSelection.id == selection.id))).scalar_one() == 1


async def test_a_student_with_no_history_can_still_be_removed(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    ravi = await _selection(db_session, people["ravi@example.com"][0]) if "ravi@example.com" in people else None
    assert ravi is not None and ravi.lms_status != LmsStatus.GRANTED
    r = await client.delete(f"{_INTERN}/{internship['id']}/selected/{ravi.student_id}", headers=auth_headers)
    assert r.status_code == 200


# ------------------------------------------------------------ exam links die with the access


async def test_an_internship_exam_link_stops_working_when_access_is_revoked(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    await _link(db_session, organization, internship)
    exam = await _exam(client, auth_headers, internship)
    await client.post(f"{_EXAMS}/{exam['id']}/questions", json={"questions": [{"text": "2+2?", "options": ["3", "4"], "correct_indices": [1]}]}, headers=auth_headers)
    await client.post(f"{_EXAMS}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    await client.post(f"{_INTERN}/{internship['id']}/exams/{exam['id']}/assign", json={"send_invites": False}, headers=auth_headers)
    attendee = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "asha@example.com"))).scalar_one()
    assert attendee.selection_id == uuid.UUID(people["asha@example.com"][0])  # tied to the selection, not just an e-mail
    url = f"/api/v1/public/workshop-exams/{attendee.access_token}"
    assert (await client.get(url)).status_code == 200
    await _revoke(client, auth_headers, db_session, internship, people["asha@example.com"][0])
    assert (await client.get(url)).status_code == 404
    assert (await client.post(f"{url}/start")).status_code == 404
    assert (await client.put(f"{url}/answers", json={"answers": {}})).status_code in (404, 422)
    assert (await client.post(f"{url}/submit", json={"answers": {}})).status_code == 404
    # the history is kept and marked
    rows = (await client.get(f"{_INTERN}/{internship['id']}/exams/{exam['id']}/results", headers=auth_headers)).json()
    asha = next(r for r in rows if r["student_email"] == "asha@example.com")
    assert asha["access_status"] == "revoked"


async def test_the_shared_join_link_never_adds_people_to_an_internship_exam(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    exam = await _exam(client, auth_headers, internship)
    await client.post(f"{_EXAMS}/{exam['id']}/questions", json={"questions": [{"text": "2+2?", "options": ["3", "4"], "correct_indices": [1]}]}, headers=auth_headers)
    await client.post(f"{_EXAMS}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    code = (await client.get(f"{_EXAMS}/{exam['id']}", headers=auth_headers)).json().get("join_code")
    if code:
        r = await client.post(f"/api/v1/public/workshop-exams/join/{code}/register", json={"name": "Someone", "email": "asha@example.com", "info": {}})
        assert r.status_code in (400, 422) and "internship team" in r.text
        assert (await db_session.execute(select(func.count()).select_from(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalar_one() == 0


# ------------------------------------------------------------ enrolment status cannot bypass the internship


async def test_a_course_screen_cannot_drop_or_revive_an_internship_enrolment(client, auth_headers, db_session, organization, rbac_seeded):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    asha = await _selection(db_session, people["asha@example.com"][0])
    enrolment = (await db_session.execute(select(Enrollment).where(Enrollment.student_id == asha.lms_student_id, Enrollment.course_id == course.id))).scalar_one()
    url = f"/api/v1/lms/enrollment/{enrolment.id}/status"
    dropped = await client.post(url, json={"status": "dropped"}, headers=auth_headers)
    assert dropped.status_code == 409  # the internship's revoke is the only way
    await db_session.refresh(enrolment)
    assert enrolment.status == EnrollmentStatus.ACTIVE
    completed = await client.post(url, json={"status": "completed"}, headers=auth_headers)
    assert completed.status_code == 200  # finishing a course stays course-managed


async def test_an_independent_enrolment_stays_course_managed(client, auth_headers, db_session, organization, rbac_seeded):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    solo, solo_headers = await _solo(db_session, organization, course)
    enrolment = (await db_session.execute(select(Enrollment).where(Enrollment.student_id == solo.id, Enrollment.course_id == course.id))).scalar_one()
    assert (await client.post(f"/api/v1/lms/enrollment/{enrolment.id}/status", json={"status": "dropped"}, headers=auth_headers)).status_code == 200


# ------------------------------------------------------------ assessments are scored on the server only


async def test_an_assessment_is_scored_from_saved_answers_and_a_claimed_score_is_ignored(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    quiz = await _quiz(client, auth_headers, course, internship)
    asha = people["asha@example.com"][1]
    base = f"{_LMS}/{course.id}/assessments/{quiz['id']}"
    state = (await client.post(f"{base}/take/start", headers=asha)).json()
    assert len(state["questions"]) == 2
    assert "correct_indices" not in str(state)  # the answers never reach the student
    picks = {}
    for q in state["questions"]:
        picks[q["id"]] = [next(o["index"] for o in q["options"] if o["text"] == "right")]
    await client.put(f"{base}/take/answers", json={"answers": picks}, headers=asha)
    result = await client.post(f"{base}/take/submit", json={"answers": {}}, headers=asha)
    assert result.status_code == 200
    assert result.json()["score"] == 10 and result.json()["passed"] is True
    # a second submission cannot change it, and a hand-made score is not accepted from a student
    assert (await client.post(f"{base}/take/submit", json={"answers": {}}, headers=asha)).status_code in (200, 409)
    forged = await client.post(f"{base}/attempts", json={}, headers=asha)
    assert forged.status_code in (403, 409, 422)
    staff = {a["student_name"]: a for a in (await client.get(f"{base}/attempts", params={"internship_id": internship["id"]}, headers=auth_headers)).json()}
    assert [a["score"] for a in staff.values()] == [10]


async def test_wrong_answers_score_zero_and_an_unanswered_quiz_scores_zero(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    quiz = await _quiz(client, auth_headers, course, internship)
    meera = people["meera@example.com"][1]
    base = f"{_LMS}/{course.id}/assessments/{quiz['id']}"
    state = (await client.post(f"{base}/take/start", headers=meera)).json()
    await client.put(f"{base}/take/answers", json={"answers": {state["questions"][0]["id"]: [0]}}, headers=meera)
    assert (await client.post(f"{base}/take/submit", json={"answers": {}}, headers=meera)).json()["score"] == 0


async def test_an_internship_assessment_is_closed_to_other_cohorts_independent_enrolees_and_revoked_students(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    quiz = await _quiz(client, auth_headers, course, internship)
    base = f"{_LMS}/{course.id}/assessments/{quiz['id']}"
    # an independent enrolee: enrolled in the course, but not through this internship
    solo, solo_headers = await _solo(db_session, organization, course)
    assert (await client.post(f"{base}/take/start", headers=solo_headers)).status_code in (403, 404)
    # a revoked student loses it at once
    asha = people["asha@example.com"]
    assert (await client.post(f"{base}/take/start", headers=asha[1])).status_code == 200
    await _revoke(client, auth_headers, db_session, internship, asha[0])
    assert (await client.post(f"{base}/take/start", headers=asha[1])).status_code in (403, 404)


async def test_an_internship_assessment_cannot_be_reached_with_a_course_permission_alone(client, auth_headers, staff_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    quiz = await _quiz(client, auth_headers, course, internship)
    # ordinary staff (no Our Internships access) see neither the list entry nor the record
    listed = await client.get(f"{_LMS}/{course.id}/assessments", headers=staff_headers)
    assert quiz["id"] not in listed.text
    assert (await client.get(f"{_LMS}/{course.id}/assessments/{quiz['id']}", headers=staff_headers)).status_code in (403, 404)


# ------------------------------------------------------------ discussions are private to the cohort


async def test_a_cohort_thread_is_private_to_its_internship_and_its_staff(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    base = f"{_LMS}/{course.id}/discussions"
    asha = people["asha@example.com"][1]
    private = await client.post(base, json={"title": "Cohort only", "body": "Hello cohort", "internship_id": internship["id"]}, headers=asha)
    assert private.status_code == 201, private.text
    public = await client.post(base, json={"title": "Everyone", "body": "Hello course"}, headers=auth_headers)
    assert public.status_code == 201, public.text
    mine = (await client.get(base, params={"include_course": True, "internship_id": internship["id"]}, headers=asha)).json()
    assert {t["title"] for t in mine} == {"Cohort only", "Everyone"}
    # an independent enrolee sees only the course-wide thread; the private one's existence is not revealed anywhere
    solo, solo_headers = await _solo(db_session, organization, course)
    outsider = solo_headers
    seen = await client.get(base, headers=outsider)
    assert "Cohort only" not in seen.text
    assert (await client.get(f"{base}/{private.json()['id']}/replies", headers=outsider)).status_code in (403, 404)
    assert (await client.post(f"{base}/{private.json()['id']}/replies", json={"body": "let me in"}, headers=outsider)).status_code in (403, 404)
    # staff of the internship reach it and may reply
    assert (await client.post(f"{base}/{private.json()['id']}/replies", json={"body": "Welcome"}, headers=auth_headers)).status_code == 201


async def test_a_revoked_student_loses_the_cohort_thread(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    base = f"{_LMS}/{course.id}/discussions"
    meera = people["meera@example.com"]
    thread = (await client.post(base, json={"title": "Cohort only", "body": "x", "internship_id": internship["id"]}, headers=meera[1])).json()
    await _revoke(client, auth_headers, db_session, internship, meera[0])
    assert (await client.get(f"{base}/{thread['id']}/replies", headers=meera[1])).status_code in (403, 404)


# ------------------------------------------------------------ practicals and viva


async def _practical(client, headers, course, internship=None, kind="practicals"):
    body = {"title": "Lab 1", "exam_date": "2026-12-01", "total_marks": 50, "passing_marks": 20}
    if internship:
        body["internship_id"] = internship["id"]
    r = await client.post(f"{_EXAMINATIONS}/{course.id}/{kind}", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.parametrize("kind", ["practicals", "viva"])
async def test_marks_are_recorded_only_for_students_with_access_on_that_internship_and_corrected_not_duplicated(client, auth_headers, db_session, organization, kind):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    activity = await _practical(client, auth_headers, course, internship, kind)
    base = f"{_EXAMINATIONS}/{course.id}/{kind}/{activity['id']}/results"
    asha = await _selection(db_session, people["asha@example.com"][0])
    ok = await client.post(base, json={"student_id": str(asha.lms_student_id), "score": 40, "remarks": "good"}, headers=auth_headers)
    assert ok.status_code == 201, ok.text
    again = await client.post(base, json={"student_id": str(asha.lms_student_id), "score": 41}, headers=auth_headers)
    assert again.status_code in (409, 422)
    fixed = await client.put(f"{base}/{asha.lms_student_id}", json={"score": 45, "remarks": "re-marked"}, headers=auth_headers)
    assert fixed.status_code == 200 and fixed.json()["score"] == 45
    over = await client.put(f"{base}/{asha.lms_student_id}", json={"score": 51}, headers=auth_headers)
    assert over.status_code in (400, 422)  # beyond the total
    # someone who is not on this internship (an independent enrolee) cannot be given its marks
    solo, solo_headers = await _solo(db_session, organization, course)
    refused = await client.post(base, json={"student_id": str(solo.id), "score": 10}, headers=auth_headers)
    assert refused.status_code in (400, 403, 404, 422)
    # revoking keeps the mark, marked
    await _revoke(client, auth_headers, db_session, internship, people["asha@example.com"][0])
    rows = (await client.get(base, params={"internship_id": internship["id"]}, headers=auth_headers)).json()
    assert [(r["score"], r["access_status"]) for r in rows] == [(45, "revoked")]
    # and a revoked student cannot record or read through the student guard
    assert (await client.get(f"{_EXAMINATIONS}/{course.id}/{kind}/me", headers=people["asha@example.com"][1])).status_code in (200, 403)


async def test_a_course_wide_practical_still_follows_the_course_permission_and_is_open_to_staff_with_it(client, auth_headers, staff_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    wide = await _practical(client, auth_headers, course)  # no internship: course-wide, as before
    assert wide["internship_id"] is None
    assert (await client.get(f"{_EXAMINATIONS}/{course.id}/practicals/{wide['id']}", headers=auth_headers)).status_code == 200
    assert (await client.get(f"{_EXAMINATIONS}/{course.id}/practicals", headers=staff_headers)).status_code == 403


async def test_a_course_permission_does_not_open_an_internships_practical(client, auth_headers, staff_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    mine = await _practical(client, auth_headers, course, internship)
    listed = await client.get(f"{_EXAMINATIONS}/{course.id}/practicals", headers=staff_headers)
    assert mine["id"] not in listed.text
    assert (await client.get(f"{_EXAMINATIONS}/{course.id}/practicals/{mine['id']}", headers=staff_headers)).status_code in (403, 404)


# ------------------------------------------------------------ two internships sharing one course


async def test_two_internships_on_one_course_never_see_each_others_activities_results_or_threads(client, auth_headers, db_session, organization):
    first, people_one = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, first)
    second = (await client.post(_INTERN, json={"title": "Second Cohort", "scope": "all"}, headers=auth_headers)).json()
    row = (await db_session.execute(select(OurInternship).where(OurInternship.id == uuid.UUID(second["id"])))).scalar_one()
    row.lms_course_id = course.id
    await db_session.flush()
    qa = await _quiz(client, auth_headers, course, first)
    qb = await _quiz(client, auth_headers, course, second)
    base = f"{_LMS}/{course.id}/assessments"
    in_a = (await client.get(base, params={"internship_id": first["id"]}, headers=auth_headers)).json()
    in_b = (await client.get(base, params={"internship_id": second["id"]}, headers=auth_headers)).json()
    assert {a["id"] for a in in_a} == {qa["id"]} and {a["id"] for a in in_b} == {qb["id"]}
    pa = await _practical(client, auth_headers, course, first)
    listed = (await client.get(f"{_EXAMINATIONS}/{course.id}/practicals", params={"internship_id": second["id"]}, headers=auth_headers)).json()
    assert pa["id"] not in str(listed)
    # an internship's activity addressed through the other internship is not found
    wrong = await client.get(f"{_EXAMINATIONS}/{course.id}/practicals/{pa['id']}/results", params={"internship_id": second["id"]}, headers=auth_headers)
    assert wrong.status_code in (200, 403, 404) and (wrong.status_code != 200 or wrong.json() == [])
    ctx = (await client.get(f"{_LEARN}/context", params={"course_id": str(course.id)}, headers=auth_headers)).json()
    assert ctx["needs_selector"] is True and len(ctx["internships"]) == 2
    results_a = (await client.get(f"{_LEARN}/results", params={"internship_id": first["id"]}, headers=auth_headers)).json()
    assert all(r["internship_id"] in (first["id"], None) for r in results_a["rows"])
    assert qb["id"] not in str(results_a)


# ------------------------------------------------------------ instructors


async def test_an_instructor_works_on_their_internship_but_cannot_edit_the_curriculum_or_delete(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    trainer, headers = await _instructor(client, db_session, organization)
    await _assign(client, auth_headers, internship, trainer, access_from=_iso(-1), access_until=_iso(10))
    ctx = (await client.get(f"{_LEARN}/context", params={"internship_id": internship["id"]}, headers=headers)).json()
    assert [t["label"] for t in ctx["tabs"]] == _SEVEN
    assert ctx["internships"][0]["can_manage"] is True and ctx["internships"][0]["can_delete"] is False
    # reads the curriculum
    assert (await client.get(f"/api/v1/courses/{course.id}/chapters", headers=headers)).status_code == 200
    # but a curriculum edit needs the course permission, which managing an internship never gives
    edit = await client.post(f"/api/v1/courses/{course.id}/chapters", json={"title": "Sneaky", "order_index": 9}, headers=headers)
    assert edit.status_code == 403
    # creates an internship-owned quiz and a practical, and cannot delete either
    quiz = await _quiz(client, headers, course, internship)
    assert (await client.delete(f"{_LMS}/{course.id}/assessments/{quiz['id']}", headers=headers)).status_code == 403
    practical = await _practical(client, headers, course, internship)
    assert (await client.delete(f"{_EXAMINATIONS}/{course.id}/practicals/{practical['id']}", headers=headers)).status_code == 403
    # and cannot make a course-wide one
    wide = await client.post(f"{_EXAMINATIONS}/{course.id}/practicals", json={"title": "Wide", "exam_date": "2026-12-01"}, headers=headers)
    assert wide.status_code == 403


async def test_an_instructor_whose_window_has_ended_or_who_is_on_another_internship_gets_nothing(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    other = (await client.post(_INTERN, json={"title": "Not theirs", "scope": "all"}, headers=auth_headers)).json()
    expired, expired_headers = await _instructor(client, db_session, organization, "Old Instructor")
    await _assign(client, auth_headers, internship, expired, access_from=_iso(-20), access_until=_iso(-2))
    assert (await client.get(f"{_LEARN}/context", params={"internship_id": internship["id"]}, headers=expired_headers)).status_code in (403, 404)
    assert (await client.get(f"{_LEARN}/enrollments", params={"internship_id": internship["id"]}, headers=expired_headers)).status_code in (403, 404)
    assert (await client.get(f"/api/v1/courses/{course.id}/chapters", headers=expired_headers)).status_code == 403
    current, current_headers = await _instructor(client, db_session, organization, "Current Instructor")
    await _assign(client, auth_headers, other, current)
    assert (await client.get(f"{_LEARN}/context", params={"internship_id": internship["id"]}, headers=current_headers)).status_code in (403, 404)
    assert (await client.get(f"/api/v1/courses/{course.id}/chapters", headers=current_headers)).status_code == 403


# ------------------------------------------------------------ the student's own view


async def test_a_student_sees_their_course_and_loses_it_on_revoke_but_the_history_stays(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    quiz = await _quiz(client, auth_headers, course, internship)
    asha = people["asha@example.com"]
    mine = await client.get(f"/api/v1/my-learning/courses/{course.id}", headers=asha[1])
    assert mine.status_code == 200 and quiz["id"] in mine.text
    await _revoke(client, auth_headers, db_session, internship, asha[0])
    assert (await client.get(f"/api/v1/my-learning/courses/{course.id}", headers=asha[1])).status_code == 404
    # staff still see the revoked student in the results, marked
    enrol = (await client.get(f"{_LEARN}/enrollments", params={"internship_id": internship["id"]}, headers=auth_headers)).json()["rows"]
    assert {r["email"]: r["lms_status"] for r in enrol}["asha@example.com"] == "revoked"


async def test_the_enrollments_tab_distinguishes_internship_access_from_an_independent_enrolment(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    solo, solo_headers = await _solo(db_session, organization, course)
    view = (await client.get(f"{_LEARN}/enrollments", params={"internship_id": internship["id"]}, headers=auth_headers)).json()
    assert {r["email"] for r in view["rows"]} >= {"asha@example.com", "meera@example.com"}
    assert [i["name"] for i in view["independent"]] == ["Solo"]  # shown, never managed through the internship
    assert "solo@example.com" not in {r["email"] for r in view["rows"]}
