"""
Linking an existing exam or hackathon to an event fetches its people (and so their scores), and the students of an
internship are managed from the internship itself.

What must hold: the people of a linked exam or hackathon become students of the event's institution (an existing student is
reused by email and never renamed), their marks and team scores then show against them, syncing again never duplicates, and
everything done from an internship stays inside that internship's institution or event.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from modules.hackathons.models import ProblemStatement, TaskSubmission, Team, TeamMember
from modules.institutions.models import InstitutionStudent
from modules.workshop_exams.models import WorkshopExamAttendee
from tests.api.test_our_internships import (
    _erpx_student,
    _event,
    _import,
    _institution,
    _internship,
    _performance,
)

pytestmark = pytest.mark.api

_INST = "/api/v1/institutions"
_EVENTS = "/api/v1/institution-events"
_INTERN = "/api/v1/our-internships"


@pytest.fixture
def org_id(superuser, organization):
    return organization.id


async def _loose_exam(client, headers, db_session, people: dict[str, tuple[int, int] | None], title="Existing exam"):
    """An exam that belongs to no event, with attendees; ``people`` maps email -> (score, total) or None for did-not-sit."""
    r = await client.post("/api/v1/workshop-exams", json={"title": title, "duration_minutes": 30}, headers=headers)
    assert r.status_code == 201, r.text
    exam = r.json()
    questions = [{"text": f"Q{i}", "options": ["a", "b"], "correct_indices": [0], "marks": 5} for i in range(2)]
    assert (await client.post(f"/api/v1/workshop-exams/{exam['id']}/questions", json={"questions": questions}, headers=headers)).status_code in (200, 201)
    await client.post(
        f"/api/v1/workshop-exams/{exam['id']}/attendees",
        json={"attendees": [{"name": email.split("@")[0].title(), "email": email} for email in people]},
        headers=headers,
    )
    for row in (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalars():
        result = people[row.email]
        if result is not None:
            row.submitted_at = datetime.now(timezone.utc)
            row.score, row.total_marks = result
    await db_session.flush()
    return exam


async def _loose_hackathon(client, headers, db_session, organization_id, teams: dict[str, tuple[list[tuple[str, str | None]], int | None]]):
    """A hackathon that belongs to no event, with teams: name -> ([(member name, email)], score or None)."""
    r = await client.post(
        "/api/v1/hackathons",
        json={"code": f"HK-{uuid.uuid4().hex[:6]}", "title": "Existing Hackathon", "registration_deadline": "2026-11-09", "start_date": "2026-11-12", "end_date": "2026-11-12"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    hackathon = r.json()
    hid = uuid.UUID(hackathon["id"])
    task = ProblemStatement(hackathon_id=hid, title="Build it", marks=100)
    db_session.add(task)
    await db_session.flush()
    for name, (members, score) in teams.items():
        people = []
        for n, e in members:
            student = await _erpx_student(db_session, organization_id, n, e or f"x-{uuid.uuid4().hex[:6]}@example.com")
            if e is None:
                student.email = None
            people.append(student)
        team = Team(hackathon_id=hid, created_by_student_id=people[0].id, name=name, join_code=uuid.uuid4().hex[:8])
        db_session.add(team)
        await db_session.flush()
        for person in people:
            db_session.add(TeamMember(team_id=team.id, student_id=person.id, joined_at=datetime.now(timezone.utc)))
        if score is not None:
            db_session.add(TaskSubmission(team_id=team.id, problem_statement_id=task.id, submitted_at=datetime.now(timezone.utc), score=score))
    await db_session.flush()
    return hackathon


def _by_email(board):
    return {s["email"]: s for s in board["students"]}


async def _count(db_session, institution_id):
    return (await db_session.execute(select(func.count()).select_from(InstitutionStudent).where(InstitutionStudent.institution_id == uuid.UUID(institution_id)))).scalar_one()


# ------------------------------------------------------------ linking an existing exam or hackathon


def _cands(response):
    assert response.status_code == 200, response.text
    return {c["email"]: c for c in response.json()["candidates"]}


async def _candidates(client, headers, event):
    return await client.get(f"{_EVENTS}/{event['id']}/student-candidates", headers=headers)


async def _add(client, headers, event, *items):
    return await client.post(f"{_EVENTS}/{event['id']}/student-candidates/add", json={"items": [dict(i) for i in items]}, headers=headers)


async def test_linking_an_exam_adds_nobody_until_they_are_verified(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (8, 10), "meera@example.com": (4, 10), "kiran@example.com": None})
    linked = await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    assert linked.status_code == 200, linked.text
    assert "3 people found (3 new)" in linked.json()["message"] and "Validate students" in linked.json()["message"]
    assert await _count(db_session, inst["id"]) == 0  # found, not added
    assert _by_email(await _performance(client, auth_headers, await _internship(client, auth_headers))) == {}
    found = _cands(await _candidates(client, auth_headers, event))
    assert set(found) == {"asha@example.com", "meera@example.com", "kiran@example.com"} and all(c["status"] == "new" and c["addable"] for c in found.values())
    assert found["asha@example.com"]["sources"] == [{"kind": "exam", "title": "Existing exam"}]
    assert await _count(db_session, inst["id"]) == 0  # looking does not add either


async def test_verified_people_are_added_and_their_marks_then_show(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (8, 10), "meera@example.com": (4, 10), "kiran@example.com": None})
    await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    added = await _add(client, auth_headers, event, {"email": "asha@example.com"}, {"email": "meera@example.com"})
    assert added.status_code == 200 and (added.json()["registered"], added.json()["new_students"], added.json()["skipped"]) == (2, 2, 0)
    rows = _by_email(await _performance(client, auth_headers, await _internship(client, auth_headers)))
    assert set(rows) == {"asha@example.com", "meera@example.com"}  # Kiran was not verified, so he is not added
    assert (rows["asha@example.com"]["exam_score"], rows["asha@example.com"]["exam_total"]) == (8, 10) and rows["meera@example.com"]["exam_percent"] == 40.0
    left = _cands(await _candidates(client, auth_headers, event))
    assert left["asha@example.com"]["status"] == "registered" and left["asha@example.com"]["addable"] is False and left["kiran@example.com"]["status"] == "new"


async def test_the_same_person_in_several_places_is_combined_by_email_and_everyone_else_is_left_alone(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    one = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (8, 10), "meera@example.com": (4, 10)}, title="First exam")
    two = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (9, 10), "kiran@example.com": None}, title="Second exam")
    for row in (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "asha@example.com"))).scalars():
        row.name = "Asha Rao" if row.exam_id == uuid.UUID(one["id"]) else "Asha R"
    await db_session.flush()
    hackathon = await _loose_hackathon(client, auth_headers, db_session, org_id, {"Alpha": ([("Asha Rao", "ASHA@example.com "), ("Ravi Kumar", "ravi@example.com")], 80)})
    for exam in (one, two):
        await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    linked = await client.put(f"{_EVENTS}/{event['id']}/hackathons/{hackathon['id']}", headers=auth_headers)
    assert "4 people found" in linked.json()["message"]  # asha x3 -> one, meera, kiran, ravi
    found = _cands(await _candidates(client, auth_headers, event))
    assert set(found) == {"asha@example.com", "meera@example.com", "kiran@example.com", "ravi@example.com"}
    asha = found["asha@example.com"]
    assert asha["entries"] == 3 and asha["name"] == "Asha Rao" and asha["name_variants"] == ["Asha R"] and "name_variants" in asha["issues"]
    assert {(s["kind"], s["title"]) for s in asha["sources"]} == {("exam", "First exam"), ("exam", "Second exam"), ("hackathon", "Existing Hackathon")}
    assert found["meera@example.com"]["entries"] == 1 and found["meera@example.com"]["name_variants"] == []  # the rest are left as they are
    added = await _add(client, auth_headers, event, *({"email": e} for e in found))
    assert added.json()["registered"] == 4 and await _count(db_session, inst["id"]) == 4  # Asha is one student, not three
    asha_row = _by_email(await _performance(client, auth_headers, await _internship(client, auth_headers)))["asha@example.com"]
    assert asha_row["team"]["score"] == 80 and asha_row["exam_score"] is not None


async def test_a_corrected_name_is_used_for_new_people_and_existing_students_keep_theirs(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event, other = await _event(client, auth_headers, inst), await _event(client, auth_headers, inst, "Earlier workshop")
    await _import(client, auth_headers, other, "Name,Email\nAsha Rao,asha@example.com\n")
    exam = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (9, 10), "new@example.com": (5, 10)})
    await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    found = _cands(await _candidates(client, auth_headers, event))
    assert found["asha@example.com"]["status"] == "at_institution" and found["asha@example.com"]["existing_name"] == "Asha Rao"
    assert "name_differs" in found["asha@example.com"]["issues"] and found["new@example.com"]["status"] == "new"
    await _add(client, auth_headers, event, {"email": "asha@example.com", "name": "Someone Else"}, {"email": "new@example.com", "name": "  Nina   Patel ", "phone": "99"})
    people = {s.email: s for s in (await db_session.execute(select(InstitutionStudent))).scalars()}
    assert people["asha@example.com"].name == "Asha Rao"  # an existing student is never renamed
    assert (people["new@example.com"].name, people["new@example.com"].phone) == ("Nina Patel", "99")
    assert await _count(db_session, inst["id"]) == 2


async def test_only_people_on_the_review_list_can_be_added_and_each_only_once(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (8, 10)})
    await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    added = await _add(client, auth_headers, event, {"email": "asha@example.com"}, {"email": "ASHA@example.com"}, {"email": "stranger@example.com"}, {"email": "x@y"})
    assert (added.json()["registered"], added.json()["skipped"]) == (1, 2)  # the duplicate is one person; strangers are refused
    assert await _count(db_session, inst["id"]) == 1
    again = await _add(client, auth_headers, event, {"email": "asha@example.com"})
    assert again.json()["registered"] == 0 and again.json()["skipped"] == 1 and "Nobody was added" in again.json()["message"]
    assert await _count(db_session, inst["id"]) == 1
    assert (await client.post(f"{_EVENTS}/{event['id']}/student-candidates/add", json={"items": []}, headers=auth_headers)).status_code in (400, 422)


async def test_a_bad_email_is_flagged_and_cannot_be_added_and_people_without_an_email_are_listed_apart(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _loose_exam(client, auth_headers, db_session, {"good@example.com": (8, 10), "bad@example.com": (4, 10)})
    for a in (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "bad@example.com"))).scalars():
        a.email = "broken@example"  # the attendee import refuses this, but old or hand-edited data can hold it
    await db_session.flush()
    hackathon = await _loose_hackathon(client, auth_headers, db_session, org_id, {"Solo": ([("No Mail", None), ("Has Mail", "has@example.com")], 50)})
    await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    await client.put(f"{_EVENTS}/{event['id']}/hackathons/{hackathon['id']}", headers=auth_headers)
    body = (await _candidates(client, auth_headers, event)).json()
    found = {c["email"]: c for c in body["candidates"]}
    assert "invalid_email" in found["broken@example"]["issues"] and found["broken@example"]["addable"] is False
    assert found["good@example.com"]["addable"] is True and found["has@example.com"]["addable"] is True
    assert [(n["name"], n["source"]["kind"]) for n in body["without_email"]] == [("No Mail", "hackathon")]
    assert "1 without an email" in body["message"]
    added = await _add(client, auth_headers, event, {"email": "broken@example"}, {"email": "good@example.com"})
    assert (added.json()["registered"], added.json()["skipped"]) == (1, 1)


async def test_a_hackathon_is_reviewed_and_added_then_its_team_scores_show(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    hackathon = await _loose_hackathon(
        client, auth_headers, db_session, org_id,
        {"Alpha": ([("Asha Rao", "asha@example.com"), ("Meera Iyer", "meera@example.com")], 80), "Beta": ([("Ravi Kumar", "ravi@example.com")], 92)},
    )
    linked = await client.put(f"{_EVENTS}/{event['id']}/hackathons/{hackathon['id']}", headers=auth_headers)
    assert linked.status_code == 200 and "3 people found" in linked.json()["message"]
    found = _cands(await _candidates(client, auth_headers, event))
    assert all(c["sources"] == [{"kind": "hackathon", "title": "Existing Hackathon"}] for c in found.values())
    await _add(client, auth_headers, event, *({"email": e} for e in found))
    internship = await _internship(client, auth_headers)
    board = await _performance(client, auth_headers, internship)
    rows = _by_email(board)
    assert rows["asha@example.com"]["team"]["team_name"] == "Alpha" and rows["asha@example.com"]["team"]["score"] == 80 and rows["ravi@example.com"]["team"]["rank"] == 1
    teams = {t["team_name"]: t for t in board["teams"] if t["team_id"]}
    assert all(m["student_id"] for m in teams["Alpha"]["members"])


async def test_attendee_emails_in_any_case_match_and_certificate_only_people_are_left_out(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (7, 10), "gift@example.com": None})
    for a in (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalars():
        if a.email == "asha@example.com":
            a.email = "Asha@Example.COM "  # as a person might have typed it on the public form
        else:
            a.certificate_only = True
    await db_session.flush()
    await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    found = _cands(await _candidates(client, auth_headers, event))
    assert set(found) == {"asha@example.com"}
    await _add(client, auth_headers, event, {"email": "asha@example.com"})
    rows = _by_email(await _performance(client, auth_headers, await _internship(client, auth_headers)))
    assert set(rows) == {"asha@example.com"} and rows["asha@example.com"]["exam_score"] == 7


async def test_an_event_with_nothing_linked_has_nothing_to_validate(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    body = (await _candidates(client, auth_headers, event)).json()
    assert body["candidates"] == [] and "no exams or hackathons linked" in body["message"]


# ------------------------------------------------------------ managing students from the internship


async def test_the_destinations_follow_the_internships_scope(client, auth_headers, db_session, org_id):
    one = await _institution(client, auth_headers, name="College One")
    two = await _institution(client, auth_headers, name="College Two", location="Chennai")
    e1, e2 = await _event(client, auth_headers, one, "Workshop A"), await _event(client, auth_headers, two, "Workshop B")
    everything = await client.get(f"{_INTERN}/{(await _internship(client, auth_headers))['id']}/students/destinations", headers=auth_headers)
    assert {d["institution_name"] for d in everything.json()} == {"College One", "College Two"}
    mine = await _internship(client, auth_headers, scope="institution", institution_id=one["id"])
    only_one = (await client.get(f"{_INTERN}/{mine['id']}/students/destinations", headers=auth_headers)).json()
    assert [d["institution_name"] for d in only_one] == ["College One"] and [e["id"] for e in only_one[0]["events"]] == [e1["id"]]
    pinned = await _internship(client, auth_headers, scope="institution", institution_id=two["id"], event_id=e2["id"])
    assert [e["name"] for d in (await client.get(f"{_INTERN}/{pinned['id']}/students/destinations", headers=auth_headers)).json() for e in d["events"]] == ["Workshop B"]


async def test_a_student_is_added_to_an_event_and_an_existing_one_is_reused(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event, other = await _event(client, auth_headers, inst), await _event(client, auth_headers, inst, "Second workshop")
    internship = await _internship(client, auth_headers)
    url = f"{_INTERN}/{internship['id']}/students"
    added = await client.post(url, json={"event_id": event["id"], "name": "  Asha   Rao ", "email": "Asha@Example.com", "phone": "98765"}, headers=auth_headers)
    assert added.status_code == 201 and added.json()["created"] is True
    row = _by_email(await _performance(client, auth_headers, internship))["asha@example.com"]
    assert row["name"] == "Asha Rao" and row["event_id"] == event["id"]
    again = await client.post(url, json={"event_id": other["id"], "name": "Asha R", "email": "asha@example.com"}, headers=auth_headers)
    assert again.status_code == 201 and again.json()["created"] is False and "already at the institution" in again.json()["message"]
    assert await _count(db_session, inst["id"]) == 1
    twice = await client.post(url, json={"event_id": event["id"], "name": "Asha", "email": "asha@example.com"}, headers=auth_headers)
    assert twice.status_code == 409
    assert (await client.post(url, json={"event_id": event["id"], "name": "x", "email": "not-an-email"}, headers=auth_headers)).status_code in (400, 422)


async def test_students_can_only_be_added_inside_the_internships_scope(client, auth_headers, db_session, org_id):
    one = await _institution(client, auth_headers, name="College One")
    two = await _institution(client, auth_headers, name="College Two", location="Chennai")
    e1, e2 = await _event(client, auth_headers, one, "Event A"), await _event(client, auth_headers, two, "Event B")
    e1b = await _event(client, auth_headers, one, "Event A2")
    body = {"name": "Asha", "email": "asha@example.com"}
    by_institution = await _internship(client, auth_headers, scope="institution", institution_id=one["id"])
    assert (await client.post(f"{_INTERN}/{by_institution['id']}/students", json={**body, "event_id": e1["id"]}, headers=auth_headers)).status_code == 201
    assert (await client.post(f"{_INTERN}/{by_institution['id']}/students", json={**body, "email": "b@example.com", "event_id": e2["id"]}, headers=auth_headers)).status_code in (400, 422)
    by_event = await _internship(client, auth_headers, scope="institution", institution_id=one["id"], event_id=e1["id"])
    refused = await client.post(f"{_INTERN}/{by_event['id']}/students", json={**body, "email": "c@example.com", "event_id": e1b["id"]}, headers=auth_headers)
    assert refused.status_code in (400, 422) and "one event only" in refused.text
    assert await _count(db_session, two["id"]) == 0


async def test_a_list_is_imported_with_a_dry_run_first(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    internship = await _internship(client, auth_headers)
    url = f"{_INTERN}/{internship['id']}/students/import"
    text = "Name,Email,Phone\nAsha Rao,asha@example.com,1\nMeera Iyer,meera@example.com,2\nBad Row,not-an-email,3\n"
    dry = await client.post(url, data={"event_id": event["id"], "text": text, "dry_run": "true"}, headers=auth_headers)
    assert dry.status_code == 200 and dry.json()["new_students"] == 2 and len(dry.json()["problems"]) == 1
    assert await _count(db_session, inst["id"]) == 0
    real = await client.post(url, data={"event_id": event["id"], "text": text}, headers=auth_headers)
    assert real.status_code == 200 and real.json()["registered"] == 2
    assert set(_by_email(await _performance(client, auth_headers, internship))) == {"asha@example.com", "meera@example.com"}
    other = await _institution(client, auth_headers, name="Elsewhere", location="Pune")
    far = await _event(client, auth_headers, other, "Far")
    narrow = await _internship(client, auth_headers, scope="institution", institution_id=inst["id"])
    assert (await client.post(f"{_INTERN}/{narrow['id']}/students/import", data={"event_id": far["id"], "text": text}, headers=auth_headers)).status_code in (400, 422)


async def test_a_students_details_and_individual_score_can_be_edited(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    await _import(client, auth_headers, event, "Name,Email\nAsha Rao,asha@example.com\nMeera Iyer,meera@example.com\n")
    internship = await _internship(client, auth_headers)
    asha = _by_email(await _performance(client, auth_headers, internship))["asha@example.com"]
    url = f"{_INTERN}/{internship['id']}/students/{asha['student_id']}"
    saved = await client.patch(url, json={"event_id": event["id"], "name": "Asha R. Rao", "phone": "99999", "individual_score": 7.5, "remarks": "Led the group"}, headers=auth_headers)
    assert saved.status_code == 200, saved.text
    row = _by_email(await _performance(client, auth_headers, internship))["asha@example.com"]
    assert (row["name"], row["phone"], row["individual_score"], row["remarks"]) == ("Asha R. Rao", "99999", 7.5, "Led the group")
    clash = await client.patch(url, json={"event_id": event["id"], "email": "meera@example.com"}, headers=auth_headers)
    assert clash.status_code == 409
    assert (await client.patch(url, json={"event_id": event["id"]}, headers=auth_headers)).status_code in (400, 422)
    assert (await client.patch(url, json={"event_id": event["id"], "individual_score": -1}, headers=auth_headers)).status_code in (400, 422)
    stranger = await client.patch(f"{_INTERN}/{internship['id']}/students/{uuid.uuid4()}", json={"event_id": event["id"], "name": "Nobody"}, headers=auth_headers)
    assert stranger.status_code == 404


async def test_a_student_can_be_taken_off_the_event_unless_selected(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    await _import(client, auth_headers, event, "Name,Email\nAsha Rao,asha@example.com\nMeera Iyer,meera@example.com\n")
    internship = await _internship(client, auth_headers)
    rows = _by_email(await _performance(client, auth_headers, internship))
    asha, meera = rows["asha@example.com"]["student_id"], rows["meera@example.com"]["student_id"]
    assert (await client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": [asha]}, headers=auth_headers)).status_code == 200
    refused = await client.delete(f"{_INTERN}/{internship['id']}/students/{asha}", params={"event_id": event["id"]}, headers=auth_headers)
    assert refused.status_code == 409 and "selected list" in refused.text
    removed = await client.delete(f"{_INTERN}/{internship['id']}/students/{meera}", params={"event_id": event["id"]}, headers=auth_headers)
    assert removed.status_code == 200
    assert set(_by_email(await _performance(client, auth_headers, internship))) == {"asha@example.com"}
    assert await _count(db_session, inst["id"]) == 2  # still at the institution


async def test_the_internship_validates_only_events_in_its_scope(client, auth_headers, db_session, org_id):
    one = await _institution(client, auth_headers, name="College One")
    two = await _institution(client, auth_headers, name="College Two", location="Chennai")
    e1, e2 = await _event(client, auth_headers, one, "Event A"), await _event(client, auth_headers, two, "Event B")
    x1 = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (8, 10)}, title="Exam one")
    x2 = await _loose_exam(client, auth_headers, db_session, {"ravi@example.com": (6, 10)}, title="Exam two")
    await client.put(f"{_EVENTS}/{e1['id']}/exams/{x1['id']}", headers=auth_headers)
    await client.put(f"{_EVENTS}/{e2['id']}/exams/{x2['id']}", headers=auth_headers)
    narrow = await _internship(client, auth_headers, scope="institution", institution_id=one["id"])
    listed = (await client.get(f"{_INTERN}/{narrow['id']}/students/validation-events", headers=auth_headers)).json()
    assert [(e["event_name"], e["institution_name"]) for e in listed] == [("Event A", "College One")]
    found = await client.get(f"{_INTERN}/{narrow['id']}/students/candidates", params={"event_id": e1["id"]}, headers=auth_headers)
    assert [c["email"] for c in found.json()["candidates"]] == ["asha@example.com"]
    outside = await client.get(f"{_INTERN}/{narrow['id']}/students/candidates", params={"event_id": e2["id"]}, headers=auth_headers)
    assert outside.status_code in (400, 422)
    refused = await client.post(f"{_INTERN}/{narrow['id']}/students/candidates/add", params={"event_id": e2["id"]}, json={"items": [{"email": "ravi@example.com"}]}, headers=auth_headers)
    assert refused.status_code in (400, 422) and await _count(db_session, two["id"]) == 0
    added = await client.post(f"{_INTERN}/{narrow['id']}/students/candidates/add", params={"event_id": e1["id"]}, json={"items": [{"email": "asha@example.com"}]}, headers=auth_headers)
    assert added.status_code == 200 and added.json()["registered"] == 1
    everything = await _internship(client, auth_headers)
    all_events = (await client.get(f"{_INTERN}/{everything['id']}/students/validation-events", headers=auth_headers)).json()
    assert {e["event_name"] for e in all_events} == {"Event A", "Event B"}
    done = await client.post(f"{_INTERN}/{everything['id']}/students/candidates/add", params={"event_id": e2["id"]}, json={"items": [{"email": "ravi@example.com"}]}, headers=auth_headers)
    assert done.json()["registered"] == 1
    assert set(_by_email(await _performance(client, auth_headers, everything))) == {"asha@example.com", "ravi@example.com"}


async def test_without_the_permission_students_cannot_be_managed(client, auth_headers, staff_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    internship = await _internship(client, auth_headers)
    base = f"{_INTERN}/{internship['id']}/students"
    assert (await client.get(f"{base}/destinations", headers=staff_headers)).status_code == 403
    assert (await client.post(base, json={"event_id": event["id"], "name": "A", "email": "a@example.com"}, headers=staff_headers)).status_code == 403
    assert (await client.get(f"{base}/candidates", params={"event_id": event["id"]}, headers=staff_headers)).status_code == 403
    assert (await client.post(f"{base}/candidates/add", params={"event_id": event["id"]}, json={"items": [{"email": "a@example.com"}]}, headers=staff_headers)).status_code == 403
    assert (await client.get(f"{_EVENTS}/{event['id']}/student-candidates", headers=staff_headers)).status_code == 403
    assert (await client.post(f"{_EVENTS}/{event['id']}/student-candidates/add", json={"items": [{"email": "a@example.com"}]}, headers=staff_headers)).status_code == 403


async def test_one_organization_cannot_manage_anothers_internship_students(client, auth_headers, db_session, org_id):
    from modules.organizations.repository import OrganizationRepository
    from tests._fixtures import _make_user

    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    internship = await _internship(client, auth_headers)
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other, is_superuser=True, email=f"x-{uuid.uuid4().hex[:6]}@other.example.com")
    outsider = {"Authorization": f"Bearer {token}"}
    base = f"{_INTERN}/{internship['id']}/students"
    assert (await client.get(f"{base}/destinations", headers=outsider)).status_code == 404
    assert (await client.post(base, json={"event_id": event["id"], "name": "A", "email": "a@example.com"}, headers=outsider)).status_code == 404
    assert (await client.get(f"{_EVENTS}/{event['id']}/student-candidates", headers=outsider)).status_code == 404
    assert (await client.post(f"{_EVENTS}/{event['id']}/student-candidates/add", json={"items": [{"email": "a@example.com"}]}, headers=outsider)).status_code == 404
