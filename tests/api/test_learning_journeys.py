"""
End-to-end journeys through the real application and the real database (only object storage and e-mail are faked), made of exactly the API
calls the student portal and the trainer portal make. Not stubs: each step is the real route, its real permission check and its real
data, and what one actor does is what the other then sees. Synthetic data only.
"""

import uuid

import pytest
from sqlalchemy import select

from modules.courses.chapters.repository import ChapterRepository
from modules.courses.lessons.repository import LessonRepository
from modules.courses.resources import service as resource_service
from modules.internship_learning import files as files_module
from modules.our_internships.models import InternshipSelection
from tests.api.test_course_resource_uploads import PDF
from tests.api.test_internship_instructors import _assign, _instructor, _iso
from tests.api.test_internship_learning import FakeStorage, _INTERN, _MINE, _assignment, _exam, _publish, _submit, _url, _world, _EXAMS
from tests.api.test_learning_integration import _EXAMINATIONS, _LEARN, _LMS, _link, _quiz, _revoke, _roles, _solo  # noqa: F401

pytestmark = pytest.mark.api


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(files_module, "get_storage_client", lambda: fake)
    monkeypatch.setattr(resource_service, "get_storage_client", lambda: fake)
    return fake


async def test_the_student_journey_from_the_internship_to_the_course_and_back_then_losing_everything_on_revoke(client, auth_headers, db_session, organization, storage):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    selection_id, asha = people["asha@example.com"]
    chapter = (await ChapterRepository(db_session).list_for_course(course.id))[0]
    lesson = await LessonRepository(db_session).create(chapter_id=chapter.id, title="Recon basics", order_index=1)
    await db_session.flush()
    resources = f"/api/v1/courses/{course.id}/chapters/{chapter.id}/lessons/{lesson.id}/resources"
    await client.post(f"{resources}/upload", files={"file": ("recon.pdf", PDF, "application/pdf")}, data={"title": "Recon cheat-sheet", "resource_type": "pdf"}, headers=auth_headers)
    # staff prepare the cohort's work: a quiz, an assignment and a private discussion
    quiz = await _quiz(client, auth_headers, course, internship, questions=2)
    assignment = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship, title="Recon report"))
    # 1. My Internships shows the internship and its course, and the student opens the course
    mine = (await client.get(_MINE, headers=asha)).json()
    assert [i["title"] for i in mine] == ["Pentrix Cyber Internship"] and mine[0]["course"]["accessible"] is True
    learning = (await client.get(f"/api/v1/my-learning/courses/{course.id}", headers=asha)).json()
    assert quiz["id"] in str(learning)
    # 2. the curriculum, with its uploaded file, opens for them
    assert (await client.get(f"/api/v1/courses/{course.id}/chapters/me", headers=asha)).status_code == 200
    listed = (await client.get(resources, headers=asha)).json()
    link = await client.get(f"{resources}/{listed[0]['id']}/download", headers=asha)
    assert link.status_code == 200 and link.json()["filename"] == "recon.pdf"
    # 3. they take the quiz: the server scores it from what they saved
    base = f"{_LMS}/{course.id}/assessments/{quiz['id']}"
    state = (await client.post(f"{base}/take/start", headers=asha)).json()
    picks = {q["id"]: [next(o["index"] for o in q["options"] if o["text"] == "right")] for q in state["questions"]}
    assert (await client.put(f"{base}/take/answers", json={"answers": picks}, headers=asha)).status_code == 200
    done = (await client.post(f"{base}/take/submit", json={"answers": picks}, headers=asha)).json()
    assert done["score"] == 10 and done["passed"] is True
    assert (await client.post(f"{base}/take/start", headers=asha)).status_code in (400, 409, 422)  # once only
    # 4. they hand in the assignment, a trainer will mark it, and they see the mark
    assert (await _submit(client, asha, internship, assignment, note="Done")).status_code in (200, 201)
    graded = await client.put(_url(internship, assignment, f"/submissions/{selection_id}/grade"), json={"score": 82, "feedback": "Good recon"}, headers=auth_headers)
    assert graded.status_code == 200, graded.text
    own = (await client.get(f"{_MINE}/{internship['id']}/assignments/{assignment['id']}", headers=asha)).json()["submission"]
    assert own["score"] == 82 and own["feedback"] == "Good recon"
    # 5. they start a private cohort discussion; a student of the same course but not this internship cannot see it
    threads = f"{_LMS}/{course.id}/discussions"
    thread = (await client.post(threads, json={"title": "Stuck on nmap", "body": "Help?", "internship_id": internship["id"]}, headers=asha)).json()
    _, solo_headers = await _solo(db_session, organization, course)
    assert "Stuck on nmap" not in (await client.get(threads, headers=solo_headers)).text
    assert (await client.get(f"{threads}/{thread['id']}/replies", headers=solo_headers)).status_code in (403, 404)
    # staff and the student see the very same results
    results = (await client.get(f"{_LEARN}/results", params={"internship_id": internship["id"]}, headers=auth_headers)).json()["rows"]
    by_kind = {(r["kind"], r["student_email"]): r for r in results}
    assert by_kind[("assessment", "asha@example.com")]["score"] == 10 and by_kind[("assignment", "asha@example.com")]["score"] == 82
    # 6. access is withdrawn: every door closes for the student, and the history stays for staff, marked
    await _revoke(client, auth_headers, db_session, internship, selection_id)
    for method, url in (
        ("GET", f"/api/v1/my-learning/courses/{course.id}"),
        ("GET", f"/api/v1/courses/{course.id}/chapters/me"),
        ("GET", f"{resources}/{listed[0]['id']}/download"),
        ("POST", f"{base}/take/start"),
        ("GET", f"{threads}/{thread['id']}/replies"),
        ("GET", f"{_MINE}/{internship['id']}/assignments/{assignment['id']}"),
    ):
        assert (await client.request(method, url, headers=asha)).status_code in (403, 404), (method, url)
    after = {(r["kind"], r["student_email"]): r for r in (await client.get(f"{_LEARN}/results", params={"internship_id": internship["id"]}, headers=auth_headers)).json()["rows"]}
    assert after[("assessment", "asha@example.com")]["access_status"] == "revoked" and after[("assessment", "asha@example.com")]["score"] == 10
    assert after[("assignment", "asha@example.com")]["access_status"] == "revoked" and after[("assignment", "asha@example.com")]["score"] == 82


async def test_the_trainer_journey_assigned_internship_to_graded_work_with_the_no_delete_and_window_rules(client, auth_headers, db_session, organization, storage):
    internship, people = await _world(client, auth_headers, db_session, organization)
    course = await _link(db_session, organization, internship)
    selection_id, asha = people["asha@example.com"]
    trainer, ila = await _instructor(client, db_session, organization, "Ila Trainer")  # a login, no role: no global permission of any kind
    await _assign(client, auth_headers, internship, trainer, access_from=_iso(-1), access_until=_iso(10))
    # 1. the portal's list shows only their internship, and the Learning page's context says what they may do
    assert [i["id"] for i in (await client.get("/api/v1/instructing-internships", headers=ila)).json()] == [internship["id"]]
    ctx = (await client.get(f"{_LEARN}/context", params={"internship_id": internship["id"]}, headers=ila)).json()
    assert [t["label"] for t in ctx["tabs"]] == ["Curriculum", "Enrollments", "Evaluations", "Projects", "Discussions", "Practicals", "Viva"]
    assert ctx["internships"][0]["can_manage"] is True and ctx["internships"][0]["can_delete"] is False
    roster = (await client.get(f"{_LEARN}/enrollments", params={"internship_id": internship["id"]}, headers=ila)).json()["rows"]
    assert {r["email"] for r in roster} >= {"asha@example.com", "meera@example.com"}
    # 2. they build a quiz and publish it; the student takes it; they see the attempt
    quiz = await _quiz(client, ila, course, internship, questions=1, publish=False)
    assert (await client.patch(f"{_LMS}/{course.id}/assessments/{quiz['id']}", json={"is_published": True}, headers=ila)).status_code == 200
    base = f"{_LMS}/{course.id}/assessments/{quiz['id']}"
    state = (await client.post(f"{base}/take/start", headers=asha)).json()
    await client.post(f"{base}/take/submit", json={"answers": {state["questions"][0]["id"]: [1]}}, headers=asha)
    attempts = (await client.get(f"{base}/attempts", params={"internship_id": internship["id"]}, headers=ila)).json()
    assert [a["score"] for a in attempts] == [5]
    # 3. they mark the student's assignment
    assignment = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship))
    await _submit(client, asha, internship, assignment)
    submissions = (await client.get(_url(internship, assignment, "/submissions"), headers=ila)).json()
    assert [s["submitted"] for s in submissions if s["student_email"] == "asha@example.com"] == [True]
    assert (await client.put(_url(internship, assignment, f"/submissions/{selection_id}/grade"), json={"score": 70, "feedback": "OK"}, headers=ila)).status_code == 200
    # 4. they record a practical mark and correct it; the mark is one record, corrected not duplicated
    practical = await client.post(f"{_EXAMINATIONS}/{course.id}/practicals", json={"title": "Lab", "exam_date": "2026-12-01", "total_marks": 50, "passing_marks": 20, "internship_id": internship["id"]}, headers=ila)
    assert practical.status_code == 201, practical.text
    asha_row = await db_session.scalar(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(selection_id)))
    results_url = f"{_EXAMINATIONS}/{course.id}/practicals/{practical.json()['id']}/results"
    assert (await client.post(results_url, json={"student_id": str(asha_row.lms_student_id), "score": 30}, headers=ila)).status_code == 201
    assert (await client.put(f"{results_url}/{asha_row.lms_student_id}", json={"score": 35, "remarks": "re-marked"}, headers=ila)).status_code == 200
    rows = (await client.get(results_url, params={"internship_id": internship["id"]}, headers=ila)).json()
    assert [(r["score"], r["remarks"]) for r in rows] == [(35, "re-marked")]
    # 5. they answer in the cohort's discussion
    thread = (await client.post(f"{_LMS}/{course.id}/discussions", json={"title": "Office hours", "body": "Thursdays", "internship_id": internship["id"]}, headers=ila)).json()
    assert (await client.get(f"{_LMS}/{course.id}/discussions", params={"internship_id": internship["id"]}, headers=asha)).json()[0]["title"] == "Office hours"
    assert (await client.post(f"{_LMS}/{course.id}/discussions/{thread['id']}/replies", json={"body": "See you"}, headers=ila)).status_code == 201
    # 6. the unified results show all of it, per activity and with no combined score
    results = (await client.get(f"{_LEARN}/results", params={"internship_id": internship["id"]}, headers=ila)).json()["rows"]
    mine = {(r["kind"]): r["score"] for r in results if r["student_email"] == "asha@example.com"}
    assert {k: mine[k] for k in ("assessment", "assignment", "practical")} == {"assessment": 5, "assignment": 70, "practical": 35}
    assert not any("combined" in r or "total_score" in r for r in results)
    # 7. what they may never do: delete anything, edit the curriculum, or work on another internship
    assert (await client.delete(_url(internship, assignment), headers=ila)).status_code == 403
    assert (await client.delete(f"{base}", headers=ila)).status_code == 403
    assert (await client.delete(f"{_EXAMINATIONS}/{course.id}/practicals/{practical.json()['id']}", headers=ila)).status_code == 403
    assert (await client.post(f"/api/v1/courses/{course.id}/chapters", json={"title": "Mine", "order_index": 5}, headers=ila)).status_code == 403
    other = (await client.post(_INTERN, json={"title": "Other", "scope": "all"}, headers=auth_headers)).json()
    assert (await client.get(f"{_LEARN}/context", params={"internship_id": other["id"]}, headers=ila)).status_code in (403, 404)
    # 8. when their window ends everything closes, and what they did stays
    from modules.our_internships.instructor_models import InternshipInstructor

    window = await db_session.scalar(select(InternshipInstructor).where(InternshipInstructor.trainer_id == trainer.id))
    from datetime import datetime, timedelta, timezone

    window.access_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.flush()
    assert (await client.get("/api/v1/instructing-internships", headers=ila)).json() == []
    for url in (f"{_LEARN}/context", f"{_LEARN}/enrollments", f"{_LEARN}/results"):
        assert (await client.get(url, params={"internship_id": internship["id"]}, headers=ila)).status_code in (403, 404), url
    assert (await client.get(base, headers=ila)).status_code in (403, 404)
    assert (await client.get(f"{base}/attempts", headers=auth_headers)).json()  # the record is untouched for the administrators
