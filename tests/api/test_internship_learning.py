"""
Internship learning: the exams and assignments of an internship, and the student's own "My Internship" view.

The things that must hold: only students with LMS access on *this* internship can see or hand in its work, one student can
never see or change another's submission, deadlines and marking lock what they should, marks follow the rubric, and the
files (kept in object storage) are validated and cleaned up.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from modules.internship_learning import files as files_module
from modules.internship_learning import routes as learning_routes
from modules.internship_learning.models import InternshipFile
from modules.our_internships.models import InternshipSelection, LmsStatus
from modules.students.models import Student
from modules.workshop_exams.models import WorkshopExamAttendee
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_INST = "/api/v1/institutions"
_EVENTS = "/api/v1/institution-events"
_INTERN = "/api/v1/our-internships"
_MINE = "/api/v1/my-internships"
_EXAMS = "/api/v1/workshop-exams"
_LIST = "Name,Email,Phone\nAsha Rao,asha@example.com,9876543210\nMeera Iyer,meera@example.com,9123456789\nRavi Kumar,ravi@example.com,9000011111\n"


class FakeStorage:
    """Object storage in memory, so no MinIO is needed and every stored object can be checked."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    async def ensure_bucket(self):
        return None

    async def upload_bytes(self, key, data, content_type="application/octet-stream"):
        self.objects[key] = data

    def presigned_download_url(self, key):
        return f"https://storage.test/{key}"

    async def delete_object(self, key):
        self.objects.pop(key, None)


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(files_module, "get_storage_client", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def invites(monkeypatch):
    sent: list[uuid.UUID] = []
    monkeypatch.setattr(learning_routes, "enqueue_invites", lambda ids: sent.extend(ids))
    return sent


async def _world(client, headers, db_session, organization, enrolled=("asha@example.com", "meera@example.com")):
    """An internship with three selected students; those in ``enrolled`` have LMS access and a student login.
    Returns (internship, {email: (selection_id, student headers or None)})."""
    inst = (await client.post(_INST, json={"name": "Sri Venkateswara College", "location": "Tirupati", "faculty_name": "Dr. L"}, headers=headers)).json()
    event = (
        await client.post(
            f"{_INST}/{inst['id']}/events",
            json={"name": "Workshop", "event_type": "workshop", "start_date": "2026-11-10", "end_date": "2026-11-11"},
            headers=headers,
        )
    ).json()
    await client.post(f"{_EVENTS}/{event['id']}/students/import", data={"text": _LIST}, headers=headers)
    internship = (await client.post(_INTERN, json={"title": "Pentrix Cyber Internship", "scope": "all"}, headers=headers)).json()
    board = (await client.get(f"{_INTERN}/{internship['id']}/performance", headers=headers)).json()
    ids = {s["email"]: s["student_id"] for s in board["students"]}
    r = await client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": list(ids.values())}, headers=headers)
    assert r.status_code == 200, r.text
    people = {}
    for email, student_id in ids.items():
        selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == uuid.UUID(student_id)))).scalar_one()
        student_headers = None
        if email in enrolled:
            user, token = await _make_user(db_session, organization, is_superuser=False, email=email)
            student = Student(
                organization_id=organization.id,
                student_code=f"S-{uuid.uuid4().hex[:8]}",
                full_name=email.split("@")[0],
                email=email,
                course_name="Cyber",
                enrollment_date=date(2026, 1, 1),
                user_id=user.id,
            )
            db_session.add(student)
            await db_session.flush()
            selection.lms_status = LmsStatus.GRANTED
            selection.lms_user_id = user.id
            selection.lms_student_id = student.id
            student_headers = {"Authorization": f"Bearer {token}"}
        people[email] = (str(selection.id), student_headers)
    await db_session.flush()
    return internship, people


async def _assignment(client, headers, internship, **over):
    body = {"title": "Recon report", "description": "Map the target.", "max_marks": 100, "max_files": 3, **over}
    r = await client.post(f"{_INTERN}/{internship['id']}/assignments", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _publish(client, headers, internship, assignment):
    r = await client.patch(f"{_INTERN}/{internship['id']}/assignments/{assignment['id']}", json={"status": "published"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _url(internship, assignment, tail=""):
    return f"{_INTERN}/{internship['id']}/assignments/{assignment['id']}{tail}"


async def _submit(client, student_headers, internship, assignment, files=(("report.pdf", b"%PDF-1.4 hi"),), note=None):
    return await client.post(
        f"{_MINE}/{internship['id']}/assignments/{assignment['id']}/submission",
        data={"note": note} if note else {},
        files=[("files", (name, data, "application/pdf")) for name, data in files],
        headers=student_headers,
    )


# ------------------------------------------------------------ assignments (staff)


async def test_an_assignment_is_created_as_a_draft_edited_published_and_deleted(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    a = await _assignment(client, auth_headers, internship, tasks=[{"id": "t1", "title": "Scan", "details": "nmap"}])
    assert a["status"] == "draft" and a["tasks"][0]["title"] == "Scan" and a["enrolled_count"] == 2
    edited = await client.patch(_url(internship, a), json={"title": "Recon report v2", "allow_late": True}, headers=auth_headers)
    assert edited.status_code == 200 and edited.json()["title"] == "Recon report v2" and edited.json()["allow_late"] is True
    assert (await _publish(client, auth_headers, internship, a))["status"] == "published"
    assert len((await client.get(f"{_INTERN}/{internship['id']}/assignments", headers=auth_headers)).json()) == 1
    assert (await client.delete(_url(internship, a), headers=auth_headers)).status_code == 200
    assert (await client.get(_url(internship, a), headers=auth_headers)).status_code == 404


async def test_a_rubric_sets_the_total_marks_and_must_be_consistent(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    rubric = [{"id": "r1", "criterion": "Method", "points": 30}, {"id": "r2", "criterion": "Report", "points": 20}]
    a = await _assignment(client, auth_headers, internship, rubric=rubric, max_marks=100)
    assert a["max_marks"] == 50
    dup = await client.post(
        f"{_INTERN}/{internship['id']}/assignments",
        json={"title": "x", "rubric": [{"id": "r1", "criterion": "A", "points": 1}, {"id": "r1", "criterion": "B", "points": 1}]},
        headers=auth_headers,
    )
    assert dup.status_code == 422 or dup.status_code == 400
    bad_dates = await client.post(
        f"{_INTERN}/{internship['id']}/assignments",
        json={"title": "x", "starts_at": "2026-12-02T00:00:00Z", "deadline_at": "2026-12-01T00:00:00Z"},
        headers=auth_headers,
    )
    assert bad_dates.status_code in (400, 422)


async def test_reference_files_are_uploaded_listed_and_removed(client, auth_headers, db_session, organization, storage):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    a = await _assignment(client, auth_headers, internship)
    up = await client.post(_url(internship, a, "/files"), files={"file": ("brief.pdf", b"%PDF brief", "application/pdf")}, headers=auth_headers)
    assert up.status_code == 201, up.text
    body = up.json()
    assert body["filename"] == "brief.pdf" and body["size_bytes"] == 10 and body["url"].startswith("https://storage.test/internships/")
    assert len(storage.objects) == 1
    assert (await client.get(_url(internship, a), headers=auth_headers)).json()["files"][0]["id"] == body["id"]
    assert (await client.delete(_url(internship, a, f"/files/{body['id']}"), headers=auth_headers)).status_code == 200
    assert storage.objects == {}


async def test_uploads_are_checked_for_type_size_and_emptiness(client, auth_headers, db_session, organization, monkeypatch):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    a = await _assignment(client, auth_headers, internship)
    exe = await client.post(_url(internship, a, "/files"), files={"file": ("setup.exe", b"MZ", "application/octet-stream")}, headers=auth_headers)
    assert exe.status_code in (400, 422) and "cannot be uploaded" in exe.text
    empty = await client.post(_url(internship, a, "/files"), files={"file": ("a.txt", b"", "text/plain")}, headers=auth_headers)
    assert empty.status_code in (400, 422)
    monkeypatch.setattr(files_module, "MAX_FILE_BYTES", 10)
    big = await client.post(_url(internship, a, "/files"), files={"file": ("a.txt", b"x" * 11, "text/plain")}, headers=auth_headers)
    assert big.status_code in (400, 422) and "larger than" in big.text


async def test_a_file_name_cannot_climb_out_of_its_folder(client, auth_headers, db_session, organization, storage):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    a = await _assignment(client, auth_headers, internship)
    r = await client.post(_url(internship, a, "/files"), files={"file": ("../../etc/passwd", b"x", "text/plain")}, headers=auth_headers)
    assert r.status_code == 201 and r.json()["filename"] == "passwd"
    assert all(k.startswith(f"internships/{internship['id']}/assignment/") and ".." not in k for k in storage.objects)


# ------------------------------------------------------------ the student's side


async def test_a_student_sees_only_internships_they_are_enrolled_on(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    mine = (await client.get(_MINE, headers=asha)).json()
    assert [m["id"] for m in mine] == [internship["id"]] and mine[0]["title"] == "Pentrix Cyber Internship"
    assert (await client.get(f"{_MINE}/{internship['id']}", headers=asha)).status_code == 200
    assert (await client.get(f"{_MINE}/{uuid.uuid4()}", headers=asha)).status_code == 404


async def test_a_selected_student_without_lms_access_sees_nothing(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization, enrolled=("asha@example.com",))
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(people["asha@example.com"][0])))).scalar_one()
    selection.lms_status = LmsStatus.REVOKED
    await db_session.flush()
    asha = people["asha@example.com"][1]
    assert (await client.get(_MINE, headers=asha)).json() == []
    assert (await client.get(f"{_MINE}/{internship['id']}/assignments", headers=asha)).status_code == 404


async def test_drafts_are_hidden_from_students_until_published(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    a = await _assignment(client, auth_headers, internship)
    assert (await client.get(f"{_MINE}/{internship['id']}/assignments", headers=asha)).json() == []
    assert (await client.get(f"{_MINE}/{internship['id']}/assignments/{a['id']}", headers=asha)).status_code == 404
    assert (await _submit(client, asha, internship, a)).status_code == 404
    await _publish(client, auth_headers, internship, a)
    listed = (await client.get(f"{_MINE}/{internship['id']}/assignments", headers=asha)).json()
    assert [x["id"] for x in listed] == [a["id"]] and listed[0]["can_submit"] is True and listed[0]["submission"] is None


async def test_a_student_hands_in_work_and_it_reaches_the_staff_view(client, auth_headers, db_session, organization, storage):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    a = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship))
    r = await _submit(client, asha, internship, a, note="Done", files=(("report.pdf", b"%PDF mine"), ("notes.txt", b"hello")))
    assert r.status_code == 200, r.text
    sub = r.json()["submission"]
    assert sub["note"] == "Done" and sub["is_late"] is False and len(sub["files"]) == 2 and sub["reviewed"] is False
    assert len(storage.objects) == 2
    rows = (await client.get(_url(internship, a, "/submissions"), headers=auth_headers)).json()
    by_email = {row["student_email"]: row for row in rows}
    assert set(by_email) == {"asha@example.com", "meera@example.com"}
    assert by_email["asha@example.com"]["submitted"] is True and len(by_email["asha@example.com"]["files"]) == 2
    assert by_email["meera@example.com"]["submitted"] is False
    listing = (await client.get(f"{_INTERN}/{internship['id']}/assignments", headers=auth_headers)).json()[0]
    assert (listing["submitted_count"], listing["graded_count"], listing["enrolled_count"]) == (1, 0, 2)


async def test_resubmitting_replaces_the_files_and_a_note_alone_keeps_them(client, auth_headers, db_session, organization, storage):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    a = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship))
    await _submit(client, asha, internship, a, files=(("v1.pdf", b"one"),))
    second = await _submit(client, asha, internship, a, files=(("v2.pdf", b"two"),))
    names = [f["filename"] for f in second.json()["submission"]["files"]]
    assert names == ["v2.pdf"] and len(storage.objects) == 1
    noted = await _submit(client, asha, internship, a, files=(), note="see v2")
    assert noted.status_code == 200
    assert [f["filename"] for f in noted.json()["submission"]["files"]] == ["v2.pdf"] and noted.json()["submission"]["note"] == "see v2"
    rows = (await client.get(_url(internship, a, "/submissions"), headers=auth_headers)).json()
    assert next(r for r in rows if r["student_email"] == "asha@example.com")["resubmission_count"] == 2
    meera = people["meera@example.com"][1]
    assert (await _submit(client, meera, internship, a, files=())).status_code in (400, 422)  # first hand-in with nothing attached, no note


async def test_the_file_limit_applies(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    a = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship, max_files=2))
    r = await _submit(client, asha, internship, a, files=(("a.txt", b"1"), ("b.txt", b"2"), ("c.txt", b"3")))
    assert r.status_code in (400, 422) and "at most 2" in r.text


async def test_deadlines_close_the_assignment_unless_late_work_is_allowed(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    strict = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship, title="Strict", deadline_at=past))
    refused = await _submit(client, asha, internship, strict)
    assert refused.status_code in (400, 422) and "deadline" in refused.text.lower()
    listed = (await client.get(f"{_MINE}/{internship['id']}/assignments/{strict['id']}", headers=asha)).json()
    assert listed["can_submit"] is False
    lenient = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship, title="Lenient", deadline_at=past, allow_late=True))
    late = await _submit(client, asha, internship, lenient)
    assert late.status_code == 200 and late.json()["submission"]["is_late"] is True


async def test_an_assignment_that_has_not_opened_or_is_closed_takes_no_work(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    soon = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship, title="Soon", starts_at=future))
    assert (await _submit(client, asha, internship, soon)).status_code in (400, 422)
    closed = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship, title="Closed"))
    await client.patch(_url(internship, closed), json={"status": "closed"}, headers=auth_headers)
    assert (await _submit(client, asha, internship, closed)).status_code in (400, 422)
    visible = (await client.get(f"{_MINE}/{internship['id']}/assignments/{closed['id']}", headers=asha)).json()
    assert visible["status"] == "closed" and visible["can_submit"] is False


async def test_students_cannot_see_each_others_work(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha, meera = people["asha@example.com"][1], people["meera@example.com"][1]
    a = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship))
    await _submit(client, asha, internship, a, note="mine")
    seen_by_meera = (await client.get(f"{_MINE}/{internship['id']}/assignments/{a['id']}", headers=meera)).json()
    assert seen_by_meera["submission"] is None


async def test_a_student_of_another_internship_cannot_reach_this_one(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization, enrolled=("asha@example.com",))
    other = (await client.post(_INTERN, json={"title": "Other", "scope": "all"}, headers=auth_headers)).json()
    asha = people["asha@example.com"][1]
    assert (await client.get(f"{_MINE}/{other['id']}", headers=asha)).status_code == 404


# ------------------------------------------------------------ marking


async def test_marking_with_a_rubric_sums_the_criteria_and_locks_the_submission(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    rubric = [{"id": "r1", "criterion": "Method", "points": 30}, {"id": "r2", "criterion": "Report", "points": 20}]
    a = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship, rubric=rubric))
    await _submit(client, asha, internship, a)
    sel = people["asha@example.com"][0]
    url = _url(internship, a, f"/submissions/{sel}/grade")
    over = await client.put(url, json={"rubric_scores": {"r1": 31}}, headers=auth_headers)
    assert over.status_code in (400, 422)
    unknown = await client.put(url, json={"rubric_scores": {"zz": 1}}, headers=auth_headers)
    assert unknown.status_code in (400, 422)
    graded = await client.put(url, json={"rubric_scores": {"r1": 25, "r2": 15}, "feedback": "Solid work"}, headers=auth_headers)
    assert graded.status_code == 200, graded.text
    assert graded.json()["score"] == 40 and graded.json()["feedback"] == "Solid work" and graded.json()["reviewed_at"]
    mine = (await client.get(f"{_MINE}/{internship['id']}/assignments/{a['id']}", headers=asha)).json()["submission"]
    assert mine["reviewed"] is True and mine["score"] == 40 and mine["rubric_scores"] == {"r1": 25, "r2": 15} and mine["feedback"] == "Solid work"
    assert mine["can_resubmit"] is False
    assert (await _submit(client, asha, internship, a)).status_code in (400, 422)  # already marked
    changing = await client.patch(_url(internship, a), json={"rubric": [{"id": "r1", "criterion": "Method", "points": 10}]}, headers=auth_headers)
    assert changing.status_code == 409


async def test_marking_without_a_rubric_takes_one_score_out_of_the_maximum(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    a = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship, max_marks=50))
    await _submit(client, asha, internship, a)
    url = _url(internship, a, f"/submissions/{people['asha@example.com'][0]}/grade")
    assert (await client.put(url, json={"feedback": "no marks"}, headers=auth_headers)).status_code in (400, 422)
    assert (await client.put(url, json={"score": 51}, headers=auth_headers)).status_code in (400, 422)
    ok = await client.put(url, json={"score": 42.5}, headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["score"] == 42.5
    again = await client.put(url, json={"score": 45}, headers=auth_headers)  # marks can be corrected
    assert again.json()["score"] == 45


async def test_a_student_who_handed_nothing_in_cannot_be_marked(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    a = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship))
    r = await client.put(_url(internship, a, f"/submissions/{people['meera@example.com'][0]}/grade"), json={"score": 10}, headers=auth_headers)
    assert r.status_code == 404


async def test_deleting_an_assignment_removes_every_stored_file(client, auth_headers, db_session, organization, storage):
    internship, people = await _world(client, auth_headers, db_session, organization)
    a = await _publish(client, auth_headers, internship, await _assignment(client, auth_headers, internship))
    await client.post(_url(internship, a, "/files"), files={"file": ("brief.pdf", b"b", "application/pdf")}, headers=auth_headers)
    await _submit(client, people["asha@example.com"][1], internship, a)
    await _submit(client, people["meera@example.com"][1], internship, a)
    assert len(storage.objects) == 3
    assert (await client.delete(_url(internship, a), headers=auth_headers)).status_code == 200
    assert storage.objects == {}
    assert (await db_session.execute(select(InternshipFile))).scalars().all() == []


# ------------------------------------------------------------ exams


async def _exam(client, headers, internship=None, title="Cyber basics"):
    body = {"title": title, "duration_minutes": 20}
    if internship:
        body["internship_id"] = internship["id"]
    r = await client.post(_EXAMS, json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_an_exam_can_be_created_for_an_internship_or_linked_and_unlinked(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    own = await _exam(client, auth_headers, internship, "Made here")
    loose = await _exam(client, auth_headers, None, "Existing exam")
    listed = (await client.get(f"{_INTERN}/{internship['id']}/exams", headers=auth_headers)).json()
    assert [e["title"] for e in listed] == ["Made here"]
    available = (await client.get(f"{_INTERN}/{internship['id']}/exams/available", headers=auth_headers)).json()
    assert [e["id"] for e in available] == [loose["id"]]
    linked = await client.post(f"{_INTERN}/{internship['id']}/exams/{loose['id']}/link", headers=auth_headers)
    assert linked.status_code == 200
    assert {e["title"] for e in (await client.get(f"{_INTERN}/{internship['id']}/exams", headers=auth_headers)).json()} == {"Made here", "Existing exam"}
    assert (await client.delete(f"{_INTERN}/{internship['id']}/exams/{own['id']}/link", headers=auth_headers)).status_code == 200
    assert (await client.get(f"{_EXAMS}/{own['id']}", headers=auth_headers)).status_code == 200  # the exam itself is kept
    assert [e["title"] for e in (await client.get(f"{_INTERN}/{internship['id']}/exams", headers=auth_headers)).json()] == ["Existing exam"]


async def test_an_exam_that_belongs_elsewhere_cannot_be_linked_and_a_foreign_internship_is_refused(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    other = (await client.post(_INTERN, json={"title": "Other", "scope": "all"}, headers=auth_headers)).json()
    taken = await _exam(client, auth_headers, other)
    r = await client.post(f"{_INTERN}/{internship['id']}/exams/{taken['id']}/link", headers=auth_headers)
    assert r.status_code == 409
    nobody = await client.post(_EXAMS, json={"title": "Not mine", "internship_id": str(uuid.uuid4())}, headers=auth_headers)
    assert nobody.status_code == 404


async def test_assigning_an_exam_adds_each_enrolled_student_once_and_invites_them(client, auth_headers, db_session, organization, invites):
    internship, people = await _world(client, auth_headers, db_session, organization)
    exam = await _exam(client, auth_headers, internship)
    url = f"{_INTERN}/{internship['id']}/exams/{exam['id']}/assign"
    first = await client.post(url, json={"send_invites": True}, headers=auth_headers)
    assert first.status_code == 200 and first.json() == {"added": 2, "already_on_exam": 0, "invited": 2}
    assert len(invites) == 2
    again = await client.post(url, json={"send_invites": True}, headers=auth_headers)
    assert again.json() == {"added": 0, "already_on_exam": 2, "invited": 0}
    attendees = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalars().all()
    assert {a.email for a in attendees} == {"asha@example.com", "meera@example.com"}  # ravi has no LMS access, so he is not on it


async def test_exam_results_cover_every_enrolled_student(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    exam = await _exam(client, auth_headers, internship)
    rows = (await client.get(f"{_INTERN}/{internship['id']}/exams/{exam['id']}/results", headers=auth_headers)).json()
    assert {r["student_email"]: r["state"] for r in rows} == {"asha@example.com": "not_assigned", "meera@example.com": "not_assigned"}
    await client.post(f"{_INTERN}/{internship['id']}/exams/{exam['id']}/assign", json={"send_invites": False}, headers=auth_headers)
    attendee = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "asha@example.com"))).scalar_one()
    attendee.started_at = datetime.now(timezone.utc)
    meera = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "meera@example.com"))).scalar_one()
    meera.started_at = meera.submitted_at = datetime.now(timezone.utc)
    meera.score, meera.total_marks = 8, 10
    await db_session.flush()
    rows = {r["student_email"]: r for r in (await client.get(f"{_INTERN}/{internship['id']}/exams/{exam['id']}/results", headers=auth_headers)).json()}
    assert rows["asha@example.com"]["state"] == "in_progress" and rows["asha@example.com"]["score"] is None
    assert rows["meera@example.com"]["state"] == "submitted" and rows["meera@example.com"]["percent"] == 80.0
    summary = (await client.get(f"{_INTERN}/{internship['id']}/exams", headers=auth_headers)).json()[0]
    assert (summary["attendee_count"], summary["submitted_count"], summary["average_percent"]) == (2, 1, 80.0)


async def test_a_student_sees_their_own_exam_link_only_once_the_exam_is_open(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    asha = people["asha@example.com"][1]
    exam = await _exam(client, auth_headers, internship)
    await client.post(f"{_INTERN}/{internship['id']}/exams/{exam['id']}/assign", json={"send_invites": False}, headers=auth_headers)
    assert (await client.get(f"{_MINE}/{internship['id']}/exams", headers=asha)).json() == []  # still a draft
    q = await client.post(f"{_EXAMS}/{exam['id']}/questions", json={"questions": [{"text": "2+2?", "options": ["3", "4"], "correct_indices": [1]}]}, headers=auth_headers)
    assert q.status_code == 201, q.text
    opened = await client.post(f"{_EXAMS}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    assert opened.status_code == 200, opened.text
    mine = (await client.get(f"{_MINE}/{internship['id']}/exams", headers=asha)).json()
    token = (await db_session.execute(select(WorkshopExamAttendee.access_token).where(WorkshopExamAttendee.email == "asha@example.com"))).scalar_one()
    assert len(mine) == 1 and mine[0]["url"].endswith(f"/workshop-exam/{token}") and mine[0]["state"] == "not_started"
    meera = people["meera@example.com"][1]
    meera_token = (await db_session.execute(select(WorkshopExamAttendee.access_token).where(WorkshopExamAttendee.email == "meera@example.com"))).scalar_one()
    assert meera_token not in (await client.get(f"{_MINE}/{internship['id']}/exams", headers=asha)).text
    assert (await client.get(f"{_MINE}/{internship['id']}/exams", headers=meera)).json()[0]["url"].endswith(meera_token)


# ------------------------------------------------------------ access control


async def test_without_the_permission_staff_can_neither_see_nor_change_anything(client, auth_headers, staff_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    a = await _assignment(client, auth_headers, internship)
    assert (await client.get(f"{_INTERN}/{internship['id']}/assignments", headers=staff_headers)).status_code == 403
    assert (await client.get(f"{_INTERN}/{internship['id']}/exams", headers=staff_headers)).status_code == 403
    assert (await client.post(f"{_INTERN}/{internship['id']}/assignments", json={"title": "x"}, headers=staff_headers)).status_code == 403
    assert (await client.delete(_url(internship, a), headers=staff_headers)).status_code == 403


async def test_a_user_without_a_student_record_gets_a_clear_refusal(client, staff_headers):
    r = await client.get(_MINE, headers=staff_headers)
    assert r.status_code in (400, 422) and "student record" in r.text


async def test_one_organization_cannot_reach_anothers_assignments(client, auth_headers, db_session, organization):
    from modules.organizations.repository import OrganizationRepository

    internship, _ = await _world(client, auth_headers, db_session, organization)
    a = await _assignment(client, auth_headers, internship)
    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"x-{uuid.uuid4().hex[:6]}@other.example.com")
    outsider = {"Authorization": f"Bearer {token}"}
    assert (await client.get(_url(internship, a), headers=outsider)).status_code == 404
    assert (await client.get(f"{_INTERN}/{internship['id']}/assignments", headers=outsider)).status_code == 404
