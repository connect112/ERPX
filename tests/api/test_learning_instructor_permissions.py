"""
An internship instructor is authorized through the internship (Our Internships access during their window), not through course permissions.
These tests use instructor accounts that hold NO global LMS permission at all: every assessment and discussion workflow they are allowed
must still work, a course-only permission must never open an internship's private records, and organization, cohort and student
boundaries stay closed. Synthetic data only.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import select

from modules.lms.enrollment.repository import EnrollmentRepository
from modules.our_internships.models import InternshipSelection
from tests.api.test_course_content_access import user_with
from tests.api.test_internship_instructors import _assign, _instructor, _iso
from tests.api.test_internship_learning import _INTERN, _world
from tests.api.test_learning_integration import _LMS, _link, _quiz, _revoke, _roles, _solo  # noqa: F401  (the autouse role fixture)

pytestmark = pytest.mark.api


async def _bare_instructor(client, auth_headers, db_session, organization, internship, name="Ila Instructor", **window):
    """A trainer with a login, no role and so no global permission of any kind, assigned to ONE internship."""
    trainer, headers = await _instructor(client, db_session, organization, name)
    await _assign(client, auth_headers, internship, trainer, **window)
    return headers


async def test_an_instructor_with_no_lms_permission_runs_the_whole_assessment_workflow_on_their_internship(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    ila = await _bare_instructor(client, auth_headers, db_session, organization, internship, access_from=_iso(-1), access_until=_iso(10))
    base = f"{_LMS}/{course.id}/assessments"
    # create, list, read, add a question, edit it, publish
    quiz = await _quiz(client, ila, course, internship, questions=1, publish=False)
    listed = await client.get(base, params={"internship_id": internship["id"]}, headers=ila)
    assert listed.status_code == 200 and [a["id"] for a in listed.json()] == [quiz["id"]]
    assert (await client.get(f"{base}/{quiz['id']}", headers=ila)).status_code == 200
    questions = (await client.get(f"{base}/{quiz['id']}/questions", headers=ila)).json()
    assert len(questions) == 1
    edited = await client.put(f"{base}/{quiz['id']}/questions/{questions[0]['id']}", json={"text": "Edited?", "options": ["a", "b"], "correct_indices": [0], "marks": 2}, headers=ila)
    assert edited.status_code == 200 and edited.json()["text"] == "Edited?"
    assert (await client.patch(f"{base}/{quiz['id']}", json={"is_published": True, "title": "Renamed"}, headers=ila)).status_code == 200
    # a student takes it, and the instructor sees the attempt and the score
    asha = people["asha@example.com"][1]
    state = (await client.post(f"{base}/{quiz['id']}/take/start", headers=asha)).json()
    assert (await client.post(f"{base}/{quiz['id']}/take/submit", json={"answers": {state["questions"][0]["id"]: [0]}}, headers=asha)).status_code == 200
    attempts = (await client.get(f"{base}/{quiz['id']}/attempts", params={"internship_id": internship["id"]}, headers=ila)).json()
    assert [a["score"] for a in attempts] == [2]
    # and still never deletes
    assert (await client.delete(f"{base}/{quiz['id']}", headers=ila)).status_code == 403
    assert (await client.delete(f"{base}/{quiz['id']}/questions/{questions[0]['id']}", headers=ila)).status_code == 403


async def test_an_instructor_can_record_a_hand_scored_attempt_only_for_a_student_of_their_cohort(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    ila = await _bare_instructor(client, auth_headers, db_session, organization, internship)
    manual = await _quiz(client, ila, course, internship, questions=0)  # no questions: scored by hand
    base = f"{_LMS}/{course.id}/assessments/{manual['id']}/attempts"
    asha = await db_session.scalar(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(people["asha@example.com"][0])))
    started = await client.post(base, json={"student_id": str(asha.lms_student_id)}, headers=ila)
    assert started.status_code == 201, started.text
    scored = await client.post(f"{base}/{started.json()['id']}/submit", json={"score": 7}, headers=ila)
    assert scored.status_code == 200 and scored.json()["score"] == 7
    # an independent enrolee of the same course is not this cohort's student
    solo, _ = await _solo(db_session, organization, course)
    assert (await client.post(base, json={"student_id": str(solo.id)}, headers=ila)).status_code == 404
    # nor is a student whose access was withdrawn
    meera = await db_session.scalar(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(people["meera@example.com"][0])))
    await _revoke(client, auth_headers, db_session, internship, people["meera@example.com"][0])
    assert (await client.post(base, json={"student_id": str(meera.lms_student_id)}, headers=ila)).status_code == 404


async def test_a_course_only_permission_never_opens_an_internships_private_assessment(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    private = await _quiz(client, auth_headers, course, internship, questions=1)
    wide = await _quiz(client, auth_headers, course, None, questions=1)
    author = await user_with(db_session, organization, ["courses.view", "courses.manage", "lms.assessments.view", "lms.assessments.manage", "lms.discussions.participate"])
    base = f"{_LMS}/{course.id}/assessments"
    # the course-wide one opens, as before
    assert (await client.get(f"{base}/{wide['id']}", headers=author)).status_code == 200
    assert (await client.get(base, headers=author)).json() and private["id"] not in (await client.get(base, headers=author)).text
    assert [a["id"] for a in (await client.get(base, params={"include_course": True}, headers=author)).json()] == [wide["id"]]
    # the internship's does not, by any door
    for method, url, body in (
        ("GET", f"{base}/{private['id']}", None),
        ("GET", f"{base}/{private['id']}/questions", None),
        ("POST", f"{base}/{private['id']}/questions", {"text": "x", "options": ["a", "b"], "correct_indices": [0]}),
        ("GET", f"{base}/{private['id']}/attempts", None),
        ("PATCH", f"{base}/{private['id']}", {"title": "Hijacked"}),
        ("DELETE", f"{base}/{private['id']}", None),
        ("GET", base + f"?internship_id={internship['id']}", None),
        ("POST", base, {"title": "Sneaky", "internship_id": internship["id"]}),
    ):
        r = await client.request(method, url, json=body, headers=author)
        assert r.status_code in (403, 404), (method, url, r.status_code)
    # it is untouched
    still = (await client.get(f"{base}/{private['id']}", headers=auth_headers)).json()
    assert still["title"] == "Quiz"


async def test_an_instructor_gets_no_course_wide_assessment_and_no_other_internships(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    other = (await client.post(_INTERN, json={"title": "Other", "scope": "all"}, headers=auth_headers)).json()
    from modules.our_internships.models import OurInternship

    row = await db_session.scalar(select(OurInternship).where(OurInternship.id == uuid.UUID(other["id"])))
    row.lms_course_id = course.id
    await db_session.flush()
    wide = await _quiz(client, auth_headers, course, None, questions=1)
    theirs = await _quiz(client, auth_headers, course, internship, questions=1)
    others = await _quiz(client, auth_headers, course, other, questions=1)
    ila = await _bare_instructor(client, auth_headers, db_session, organization, internship)
    base = f"{_LMS}/{course.id}/assessments"
    assert (await client.get(f"{base}/{theirs['id']}", headers=ila)).status_code == 200
    # the course-wide list and record need the course permission
    assert (await client.get(base, headers=ila)).status_code == 403
    assert (await client.get(f"{base}/{wide['id']}", headers=ila)).status_code == 403
    assert (await client.post(base, json={"title": "Course wide"}, headers=ila)).status_code == 403  # may not create a course-wide one
    # include_course adds nothing for someone without the course permission
    both = (await client.get(base, params={"internship_id": internship["id"], "include_course": True}, headers=ila)).json()
    assert [a["id"] for a in both] == [theirs["id"]]
    # another internship's records, by its id or through this one's, are closed
    assert (await client.get(f"{base}/{others['id']}", headers=ila)).status_code in (403, 404)
    assert (await client.get(f"{base}/{others['id']}/questions", headers=ila)).status_code in (403, 404)
    assert (await client.get(base, params={"internship_id": other["id"]}, headers=ila)).status_code in (403, 404)
    assert (await client.get(f"{base}/{theirs['id']}/attempts", params={"internship_id": other["id"]}, headers=ila)).status_code in (403, 404)


async def test_an_expired_or_not_yet_started_instructor_window_closes_every_assessment_door(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    quiz = await _quiz(client, auth_headers, course, internship, questions=1)
    base = f"{_LMS}/{course.id}/assessments"
    for name, window in (("Past", dict(access_from=_iso(-20), access_until=_iso(-2))), ("Future", dict(access_from=_iso(3), access_until=_iso(30)))):
        headers = await _bare_instructor(client, auth_headers, db_session, organization, internship, name=name, **window)
        for method, url in (("GET", f"{base}/{quiz['id']}"), ("GET", f"{base}/{quiz['id']}/questions"), ("GET", f"{base}/{quiz['id']}/attempts"), ("GET", f"{base}?internship_id={internship['id']}")):
            assert (await client.request(method, url, headers=headers)).status_code in (403, 404), (name, url)
        assert (await client.post(base, json={"title": "Late", "internship_id": internship["id"]}, headers=headers)).status_code in (403, 404), name


async def test_a_student_cannot_use_the_staff_doors_or_reach_another_cohorts_assessment(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    quiz = await _quiz(client, auth_headers, course, internship, questions=1)
    asha = people["asha@example.com"][1]
    base = f"{_LMS}/{course.id}/assessments"
    assert (await client.get(f"{base}/{quiz['id']}", headers=asha)).status_code == 200  # a granted student may see it
    for method, url, body in (
        ("GET", f"{base}/{quiz['id']}/questions", None),  # the answers
        ("POST", f"{base}/{quiz['id']}/questions", {"text": "x", "options": ["a", "b"], "correct_indices": [0]}),
        ("PATCH", f"{base}/{quiz['id']}", {"title": "Mine now"}),
        ("DELETE", f"{base}/{quiz['id']}", None),
        ("GET", f"{base}/{quiz['id']}/attempts", None),
        ("POST", base, {"title": "Mine"}),
    ):
        assert (await client.request(method, url, json=body, headers=asha)).status_code == 403, (method, url)
    solo, solo_headers = await _solo(db_session, organization, course)
    assert (await client.get(f"{base}/{quiz['id']}", headers=solo_headers)).status_code in (403, 404)
    assert quiz["id"] not in (await client.get(base, headers=solo_headers)).text
    # a student of the cohort in ANOTHER organization is a stranger to all of it
    from modules.organizations.repository import OrganizationRepository
    from tests._fixtures import _make_user

    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"x-{uuid.uuid4().hex[:6]}@other.example.com")
    outsider = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{base}/{quiz['id']}", headers=outsider)).status_code == 404
    assert (await client.get(base, params={"internship_id": internship["id"]}, headers=outsider)).status_code in (403, 404)


async def test_cohort_discussions_work_for_an_instructor_with_no_lms_permission_and_stay_closed_to_course_only_staff(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    ila = await _bare_instructor(client, auth_headers, db_session, organization, internship)
    base = f"{_LMS}/{course.id}/discussions"
    thread = await client.post(base, json={"title": "Welcome", "body": "Hello cohort", "internship_id": internship["id"]}, headers=ila)
    assert thread.status_code == 201, thread.text
    tid = thread.json()["id"]
    assert (await client.post(f"{base}/{tid}/replies", json={"body": "Ask me anything"}, headers=ila)).status_code == 201
    assert [t["title"] for t in (await client.get(base, params={"internship_id": internship["id"]}, headers=ila)).json()] == ["Welcome"]
    assert (await client.get(f"{base}/{tid}/replies", headers=ila)).status_code == 200
    assert (await client.put(f"{base}/{tid}/lock", json={"is_locked": True}, headers=ila)).status_code == 200
    # but a course-wide thread needs the course permission, and the instructor has none
    assert (await client.post(base, json={"title": "Everyone", "body": "x"}, headers=ila)).status_code == 403
    assert (await client.get(base, headers=ila)).status_code == 403
    # a staff member with only the course permission cannot see or join the cohort's thread
    staff = await user_with(db_session, organization, ["courses.view", "lms.discussions.participate"])
    assert (await client.get(f"{base}/{tid}/replies", headers=staff)).status_code == 404
    assert (await client.post(f"{base}/{tid}/replies", json={"body": "hi"}, headers=staff)).status_code == 404
    assert "Welcome" not in (await client.get(base, headers=staff)).text
    # an instructor of ANOTHER internship cannot either
    other = (await client.post(_INTERN, json={"title": "Other", "scope": "all"}, headers=auth_headers)).json()
    stranger = await _bare_instructor(client, auth_headers, db_session, organization, other, name="Stranger")
    assert (await client.get(f"{base}/{tid}/replies", headers=stranger)).status_code == 404
