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


# ------------------------------------------------------------ linking an existing exam


async def test_linking_an_existing_exam_fetches_its_attendees_and_their_marks(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (8, 10), "meera@example.com": (4, 10), "kiran@example.com": None})
    assert await _count(db_session, inst["id"]) == 0
    linked = await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    assert linked.status_code == 200, linked.text
    assert "3 people found" in linked.json()["message"] and "3 added to the event (3 new to the institution)" in linked.json()["message"]
    internship = await _internship(client, auth_headers)
    rows = _by_email(await _performance(client, auth_headers, internship))
    assert set(rows) == {"asha@example.com", "meera@example.com", "kiran@example.com"}
    assert (rows["asha@example.com"]["exam_score"], rows["asha@example.com"]["exam_total"]) == (8, 10)
    assert rows["meera@example.com"]["exam_percent"] == 40.0
    assert rows["kiran@example.com"]["exam_score"] is None and rows["kiran@example.com"]["exams"][0]["attended"] is False


async def test_an_existing_student_is_reused_by_email_and_keeps_their_name(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    other = await _event(client, auth_headers, inst, name="Earlier workshop")
    await _import(client, auth_headers, other, "Name,Email\nAsha Rao,asha@example.com\n")
    exam = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (9, 10), "new@example.com": (5, 10)})
    linked = await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    assert "1 new to the institution" in linked.json()["message"]
    assert await _count(db_session, inst["id"]) == 2  # Asha reused, not duplicated
    asha = (await db_session.execute(select(InstitutionStudent).where(InstitutionStudent.email == "asha@example.com"))).scalar_one()
    assert asha.name == "Asha Rao"  # the exam's "Asha" never overwrote the registered name
    rows = _by_email(await _performance(client, auth_headers, await _internship(client, auth_headers), event_id=event["id"]))
    assert rows["asha@example.com"]["exam_score"] == 9


async def test_attendee_emails_in_any_case_still_match_and_certificate_only_people_are_left_out(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (7, 10), "gift@example.com": None})
    attendees = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalars().all()
    for a in attendees:
        if a.email == "asha@example.com":
            a.email = "Asha@Example.COM "  # as a person might have typed it on the public form
        else:
            a.certificate_only = True
    await db_session.flush()
    await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    rows = _by_email(await _performance(client, auth_headers, await _internship(client, auth_headers)))
    assert set(rows) == {"asha@example.com"} and rows["asha@example.com"]["exam_score"] == 7


# ------------------------------------------------------------ linking an existing hackathon


async def test_linking_an_existing_hackathon_fetches_participants_and_shows_team_scores(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    hackathon = await _loose_hackathon(
        client, auth_headers, db_session, org_id,
        {"Alpha": ([("Asha Rao", "asha@example.com"), ("Meera Iyer", "meera@example.com")], 80), "Beta": ([("Ravi Kumar", "ravi@example.com")], 92)},
    )
    linked = await client.put(f"{_EVENTS}/{event['id']}/hackathons/{hackathon['id']}", headers=auth_headers)
    assert linked.status_code == 200 and "3 people found" in linked.json()["message"]
    internship = await _internship(client, auth_headers)
    board = await _performance(client, auth_headers, internship)
    rows = _by_email(board)
    assert set(rows) == {"asha@example.com", "meera@example.com", "ravi@example.com"}
    assert rows["asha@example.com"]["team"]["team_name"] == "Alpha" and rows["asha@example.com"]["team"]["score"] == 80
    assert rows["ravi@example.com"]["team"]["rank"] == 1
    teams = {t["team_name"]: t for t in board["teams"] if t["team_id"]}
    assert all(m["student_id"] for m in teams["Alpha"]["members"])  # every member can now be selected from the team view


async def test_a_hackathon_person_without_an_email_is_skipped_and_counted(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    hackathon = await _loose_hackathon(client, auth_headers, db_session, org_id, {"Solo": ([("No Mail", None), ("Has Mail", "has@example.com")], 50)})
    linked = await client.put(f"{_EVENTS}/{event['id']}/hackathons/{hackathon['id']}", headers=auth_headers)
    assert "1 skipped for having no email" in linked.json()["message"]
    assert set(_by_email(await _performance(client, auth_headers, await _internship(client, auth_headers)))) == {"has@example.com"}


# ------------------------------------------------------------ syncing again


async def test_syncing_again_picks_up_people_who_joined_later_and_never_duplicates(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (8, 10)})
    await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)
    first = await client.post(f"{_EVENTS}/{event['id']}/sync-students", headers=auth_headers)
    assert first.status_code == 200 and (first.json()["newly_registered"], first.json()["already_registered"]) == (0, 1)
    await client.post(f"/api/v1/workshop-exams/{exam['id']}/attendees", json={"attendees": [{"name": "Late One", "email": "late@example.com"}]}, headers=auth_headers)
    second = await client.post(f"{_EVENTS}/{event['id']}/sync-students", headers=auth_headers)
    assert (second.json()["newly_registered"], second.json()["new_students"], second.json()["already_registered"]) == (1, 1, 1)
    assert await _count(db_session, inst["id"]) == 2
    third = await client.post(f"{_EVENTS}/{event['id']}/sync-students", headers=auth_headers)
    assert third.json()["newly_registered"] == 0 and third.json()["new_students"] == 0


async def test_syncing_an_event_with_nothing_linked_says_so(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    r = await client.post(f"{_EVENTS}/{event['id']}/sync-students", headers=auth_headers)
    assert r.status_code == 200 and r.json()["people"] == 0 and "no exams or hackathons linked" in r.json()["message"]


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


async def test_syncing_from_the_internship_covers_every_event_in_scope_only(client, auth_headers, db_session, org_id):
    one = await _institution(client, auth_headers, name="College One")
    two = await _institution(client, auth_headers, name="College Two", location="Chennai")
    e1, e2 = await _event(client, auth_headers, one, "Event A"), await _event(client, auth_headers, two, "Event B")
    x1 = await _loose_exam(client, auth_headers, db_session, {"asha@example.com": (8, 10)}, title="Exam one")
    x2 = await _loose_exam(client, auth_headers, db_session, {"ravi@example.com": (6, 10)}, title="Exam two")
    from modules.workshop_exams.models import WorkshopExam

    for exam_id, event in ((x1["id"], e1), (x2["id"], e2)):  # linked straight in the database, so nothing was fetched yet
        row = (await db_session.execute(select(WorkshopExam).where(WorkshopExam.id == uuid.UUID(exam_id)))).scalar_one()
        row.event_id = uuid.UUID(event["id"])
    await db_session.flush()
    narrow = await _internship(client, auth_headers, scope="institution", institution_id=one["id"])
    result = await client.post(f"{_INTERN}/{narrow['id']}/students/sync", headers=auth_headers)
    assert result.status_code == 200 and result.json()["newly_registered"] == 1
    assert await _count(db_session, one["id"]) == 1 and await _count(db_session, two["id"]) == 0
    everything = await _internship(client, auth_headers)
    broad = await client.post(f"{_INTERN}/{everything['id']}/students/sync", headers=auth_headers)
    assert broad.json()["newly_registered"] == 1 and broad.json()["already_registered"] == 1  # College Two's Ravi is new, Asha was done
    assert set(_by_email(await _performance(client, auth_headers, everything))) == {"asha@example.com", "ravi@example.com"}
    one_event = await client.post(f"{_INTERN}/{everything['id']}/students/sync", params={"event_id": e2["id"]}, headers=auth_headers)
    assert one_event.status_code == 200 and one_event.json()["newly_registered"] == 0


async def test_without_the_permission_students_cannot_be_managed(client, auth_headers, staff_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    internship = await _internship(client, auth_headers)
    base = f"{_INTERN}/{internship['id']}/students"
    assert (await client.get(f"{base}/destinations", headers=staff_headers)).status_code == 403
    assert (await client.post(base, json={"event_id": event["id"], "name": "A", "email": "a@example.com"}, headers=staff_headers)).status_code == 403
    assert (await client.post(f"{base}/sync", headers=staff_headers)).status_code == 403
    assert (await client.post(f"{_EVENTS}/{event['id']}/sync-students", headers=staff_headers)).status_code == 403


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
    assert (await client.post(f"{_EVENTS}/{event['id']}/sync-students", headers=outsider)).status_code == 404
