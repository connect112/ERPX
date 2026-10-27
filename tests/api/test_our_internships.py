"""
Our Internships: choosing who to select from the students of an institution's event.

The numbers shown while choosing are read live from the event's workshop exams (marks, matched to students by email) and
its hackathons (team score from scored tasks, team members by email), plus the individual score staff entered. The
shortlist can only hold students registered inside the internship's own scope.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from modules.hackathons.models import ProblemStatement, TaskSubmission, Team, TeamMember
from modules.organizations.repository import OrganizationRepository
from modules.students.models import Student
from modules.workshop_exams.models import WorkshopExamAttendee
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_INST = "/api/v1/institutions"
_EVENTS = "/api/v1/institution-events"
_INTERN = "/api/v1/our-internships"
_LIST = "Name,Email,Phone\nAsha Rao,asha@example.com,9876543210\nMeera Iyer,meera@example.com,9123456789\nRavi Kumar,ravi@example.com,9000011111\n"


async def _institution(client, headers, name="Sri Venkateswara College", location="Tirupati"):
    r = await client.post(_INST, json={"name": name, "location": location, "faculty_name": "Dr. Lakshmi"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _event(client, headers, institution, name="Workshop"):
    r = await client.post(
        f"{_INST}/{institution['id']}/events",
        json={"name": name, "event_type": "workshop", "start_date": "2026-11-10", "end_date": "2026-11-11"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _import(client, headers, event, text=_LIST):
    r = await client.post(f"{_EVENTS}/{event['id']}/students/import", data={"text": text}, headers=headers)
    assert r.status_code == 200, r.text


async def _internship(client, headers, **over):
    body = {"title": "Pentrix Summer Internship", "scope": "all", **over}
    r = await client.post(_INTERN, json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _performance(client, headers, internship, **params):
    r = await client.get(f"{_INTERN}/{internship['id']}/performance", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _student_ids(client, headers, internship, **params):
    board = await _performance(client, headers, internship, **params)
    return {s["email"]: s["student_id"] for s in board["students"]}


async def _add_exam(client, headers, db_session, event, scores: dict[str, tuple[int, int] | None]):
    """An exam on the event with two 5-mark questions; ``scores`` maps email -> (score, total) or None for did-not-sit."""
    r = await client.post("/api/v1/workshop-exams", json={"title": "Day 1 MCQ", "duration_minutes": 30, "event_id": event["id"]}, headers=headers)
    assert r.status_code == 201, r.text
    exam = r.json()
    questions = [{"text": f"Q{i}", "options": ["a", "b"], "correct_indices": [0], "marks": 5} for i in range(2)]
    assert (await client.post(f"/api/v1/workshop-exams/{exam['id']}/questions", json={"questions": questions}, headers=headers)).status_code in (200, 201)
    await client.post(
        f"/api/v1/workshop-exams/{exam['id']}/attendees",
        json={"attendees": [{"name": email.split("@")[0], "email": email} for email in scores]},
        headers=headers,
    )
    rows = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalars().all()
    for row in rows:
        result = scores[row.email]
        if result is not None:
            row.submitted_at = datetime.now(timezone.utc)
            row.score, row.total_marks = result
    await db_session.flush()
    return exam


async def _erpx_student(db_session, organization_id, name, email):
    student = Student(
        organization_id=organization_id,
        student_code=f"S-{uuid.uuid4().hex[:8]}",
        full_name=name,
        email=email,
        course_name="Cyber",
        enrollment_date=date(2026, 1, 1),
    )
    db_session.add(student)
    await db_session.flush()
    return student


async def _add_hackathon(client, headers, db_session, organization_id, event, teams: dict[str, tuple[list[tuple[str, str]], int | None]]):
    """A hackathon on the event with one 100-mark task. ``teams``: name -> ([(member name, email)], score or None)."""
    r = await client.post(
        "/api/v1/hackathons",
        json={
            "code": f"HK-{uuid.uuid4().hex[:6]}", "title": "Day 3 Hackathon", "event_id": event["id"],
            "registration_deadline": "2026-11-09", "start_date": "2026-11-12", "end_date": "2026-11-12",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    hackathon = r.json()
    hid = uuid.UUID(hackathon["id"])
    task = ProblemStatement(hackathon_id=hid, title="Build it", marks=100)
    db_session.add(task)
    await db_session.flush()
    for name, (members, score) in teams.items():
        people = [await _erpx_student(db_session, organization_id, n, e) for n, e in members]
        team = Team(hackathon_id=hid, created_by_student_id=people[0].id, name=name, join_code=uuid.uuid4().hex[:8])
        db_session.add(team)
        await db_session.flush()
        for person in people:
            db_session.add(TeamMember(team_id=team.id, student_id=person.id, joined_at=datetime.now(timezone.utc)))
        if score is not None:
            db_session.add(
                TaskSubmission(team_id=team.id, problem_statement_id=task.id, submitted_at=datetime.now(timezone.utc), score=score)
            )
    await db_session.flush()
    return hackathon


@pytest.fixture
def org_id(superuser, organization):
    return organization.id


async def _world(client, auth_headers, db_session, org_id):
    """One institution, one event with three registered students, an exam and a hackathon."""
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    await _import(client, auth_headers, event)
    await _add_exam(client, auth_headers, db_session, event, {"asha@example.com": (8, 10), "meera@example.com": (4, 10), "ravi@example.com": None})
    await _add_hackathon(
        client, auth_headers, db_session, org_id, event,
        {
            "Alpha": ([("Asha Rao", "asha@example.com"), ("Meera Iyer", "meera@example.com")], 80),
            "Beta": ([("Outsider", "outsider@example.com")], 60),
        },
    )
    return inst, event


# ------------------------------------------------------------- creating an internship


async def test_an_internship_can_be_for_one_institutions_event_or_for_all_students(client, auth_headers, db_session, org_id):
    inst, event = await _world(client, auth_headers, db_session, org_id)
    specific = await _internship(client, auth_headers, scope="institution", institution_id=inst["id"], event_id=event["id"])
    assert (specific["institution_name"], specific["event_name"]) == ("Sri Venkateswara College", "Workshop")
    assert specific["status"] == "selecting" and specific["selected_count"] == 0
    whole = await _internship(client, auth_headers, title="Everyone", scope="institution", institution_id=inst["id"])
    assert whole["event_id"] is None
    everyone = await _internship(client, auth_headers, title="Open call", scope="all")
    assert everyone["institution_id"] is None
    assert len((await client.get(_INTERN, headers=auth_headers)).json()) == 3


async def test_the_scope_must_make_sense(client, auth_headers, db_session, org_id):
    inst, event = await _world(client, auth_headers, db_session, org_id)
    other = await _institution(client, auth_headers, name="Other College", location="Chennai")
    bad = (
        {"scope": "institution"},  # which institution?
        {"scope": "all", "institution_id": inst["id"]},
        {"scope": "institution", "institution_id": other["id"], "event_id": event["id"]},  # event is at another college
    )
    for extra in bad:
        r = await client.post(_INTERN, json={"title": "X internship", **extra}, headers=auth_headers)
        assert r.status_code == 422, (extra, r.text)
    missing = await client.post(_INTERN, json={"title": "X internship", "scope": "institution", "institution_id": str(uuid.uuid4())}, headers=auth_headers)
    assert missing.status_code == 404


async def test_an_internship_can_be_renamed_closed_and_deleted(client, auth_headers):
    internship = await _internship(client, auth_headers)
    patched = await client.patch(f"{_INTERN}/{internship['id']}", json={"title": "Winter Internship", "status": "closed"}, headers=auth_headers)
    assert patched.status_code == 200 and (patched.json()["title"], patched.json()["status"]) == ("Winter Internship", "closed")
    assert (await client.patch(f"{_INTERN}/{internship['id']}", json={"title": None}, headers=auth_headers)).status_code == 422
    assert (await client.delete(f"{_INTERN}/{internship['id']}", headers=auth_headers)).status_code == 200
    assert (await client.get(f"{_INTERN}/{internship['id']}", headers=auth_headers)).status_code == 404


# ------------------------------------------------------------------ performance


async def test_the_student_view_shows_exam_marks_team_score_and_individual_score(client, auth_headers, db_session, org_id):
    inst, event = await _world(client, auth_headers, db_session, org_id)
    internship = await _internship(client, auth_headers, scope="institution", institution_id=inst["id"], event_id=event["id"])
    ids = await _student_ids(client, auth_headers, internship)
    await client.patch(f"{_EVENTS}/{event['id']}/students/{ids['asha@example.com']}", json={"individual_score": 9.5, "remarks": "Led the team"}, headers=auth_headers)

    board = await _performance(client, auth_headers, internship)
    assert board["total_students"] == 3
    assert [e["total_marks"] for e in board["exams"]] == [10]
    assert [h["max_total"] for h in board["hackathons"]] == [100]
    by_email = {s["email"]: s for s in board["students"]}

    asha = by_email["asha@example.com"]
    assert (asha["exam_score"], asha["exam_total"], asha["exam_percent"]) == (8, 10, 80.0)
    assert asha["team"]["team_name"] == "Alpha" and asha["team"]["score"] == 80 and asha["team"]["rank"] == 1
    assert (asha["individual_score"], asha["remarks"]) == (9.5, "Led the team")
    assert asha["institution_name"] == "Sri Venkateswara College" and asha["event_name"] == "Workshop"

    meera = by_email["meera@example.com"]
    assert (meera["exam_score"], meera["exam_percent"]) == (4, 40.0)
    assert meera["team"]["team_name"] == "Alpha"  # same team, same score

    ravi = by_email["ravi@example.com"]
    assert ravi["exam_score"] is None and ravi["team"] is None
    assert ravi["exams"][0]["attended"] is False  # "did not sit" is visible, not missing


async def test_the_team_view_groups_students_by_hackathon_team(client, auth_headers, db_session, org_id):
    inst, event = await _world(client, auth_headers, db_session, org_id)
    internship = await _internship(client, auth_headers, scope="institution", institution_id=inst["id"], event_id=event["id"])
    teams = (await _performance(client, auth_headers, internship))["teams"]
    assert [t["team_name"] for t in teams] == ["Alpha", "Beta", "Not in a team"]

    alpha = teams[0]
    assert (alpha["score"], alpha["max_total"], alpha["rank"], alpha["hackathon_title"]) == (80, 100, 1, "Day 3 Hackathon")
    assert [(m["name"], m["exam_score"]) for m in alpha["members"]] == [("Asha Rao", 8), ("Meera Iyer", 4)]
    assert all(m["student_id"] for m in alpha["members"])

    beta = teams[1]
    assert beta["rank"] == 2
    # a team member who is not on the registration list is shown but cannot be selected from here
    assert [(m["name"], m["student_id"]) for m in beta["members"]] == [("Outsider", None)]

    loose = teams[2]
    assert loose["team_id"] is None and [m["name"] for m in loose["members"]] == ["Ravi Kumar"]


async def test_teams_with_equal_scores_share_a_rank_and_unscored_teams_have_none(client, auth_headers, db_session, org_id):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    await _import(client, auth_headers, event, "Name,Email\nA,a@example.com\nB,b@example.com\nC,c@example.com\nD,d@example.com\n")
    await _add_hackathon(
        client, auth_headers, db_session, org_id, event,
        {"One": ([("A", "a@example.com")], 90), "Two": ([("B", "b@example.com")], 90), "Three": ([("C", "c@example.com")], 70), "Four": ([("D", "d@example.com")], None)},
    )
    internship = await _internship(client, auth_headers, scope="institution", institution_id=inst["id"], event_id=event["id"])
    ranks = {t["team_name"]: t["rank"] for t in (await _performance(client, auth_headers, internship))["teams"]}
    assert ranks == {"One": 1, "Two": 1, "Three": 3, "Four": None}


async def test_a_student_who_is_not_in_a_team_or_an_exam_still_appears(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    await _import(client, auth_headers, event)
    internship = await _internship(client, auth_headers, scope="institution", institution_id=inst["id"], event_id=event["id"])
    board = await _performance(client, auth_headers, internship)
    assert board["total_students"] == 3 and board["exams"] == [] and board["hackathons"] == [] and board["teams"] == []
    assert all(s["team"] is None and s["exam_score"] is None for s in board["students"])


async def test_students_and_teams_can_be_searched(client, auth_headers, db_session, org_id):
    inst, event = await _world(client, auth_headers, db_session, org_id)
    internship = await _internship(client, auth_headers, scope="institution", institution_id=inst["id"], event_id=event["id"])
    by_name = await _performance(client, auth_headers, internship, q="meera")
    assert [s["name"] for s in by_name["students"]] == ["Meera Iyer"]
    assert [t["team_name"] for t in by_name["teams"]] == ["Alpha"]
    by_team = await _performance(client, auth_headers, internship, q="alpha")
    assert {s["name"] for s in by_team["students"]} == {"Asha Rao", "Meera Iyer"}
    assert (await _performance(client, auth_headers, internship, q="%"))["students"] == []


async def test_an_all_students_internship_covers_every_institution_and_can_be_narrowed(client, auth_headers, db_session, org_id):
    first_inst, first_event = await _world(client, auth_headers, db_session, org_id)
    second_inst = await _institution(client, auth_headers, name="Other College", location="Chennai")
    second_event = await _event(client, auth_headers, second_inst, name="Their workshop")
    await _import(client, auth_headers, second_event, "Name,Email\nZoya,zoya@example.com\n")
    internship = await _internship(client, auth_headers, scope="all")

    everyone = await _performance(client, auth_headers, internship)
    assert {s["institution_name"] for s in everyone["students"]} == {"Sri Venkateswara College", "Other College"}
    assert everyone["total_students"] == 4
    narrowed = await _performance(client, auth_headers, internship, institution_id=second_inst["id"])
    assert [s["name"] for s in narrowed["students"]] == ["Zoya"]
    one_event = await _performance(client, auth_headers, internship, event_id=first_event["id"])
    assert one_event["total_students"] == 3


async def test_an_institution_internship_cannot_be_widened_by_the_caller(client, auth_headers, db_session, org_id):
    first_inst, first_event = await _world(client, auth_headers, db_session, org_id)
    second_inst = await _institution(client, auth_headers, name="Other College", location="Chennai")
    second_event = await _event(client, auth_headers, second_inst, name="Their workshop")
    await _import(client, auth_headers, second_event, "Name,Email\nZoya,zoya@example.com\n")
    internship = await _internship(client, auth_headers, scope="institution", institution_id=first_inst["id"], event_id=first_event["id"])
    board = await _performance(client, auth_headers, internship, institution_id=second_inst["id"], event_id=second_event["id"])
    assert {s["institution_name"] for s in board["students"]} == {"Sri Venkateswara College"}


async def test_the_same_student_in_two_events_has_a_row_for_each(client, auth_headers):
    inst = await _institution(client, auth_headers)
    workshop = await _event(client, auth_headers, inst, name="Workshop")
    other = await _event(client, auth_headers, inst, name="Seminar")
    await _import(client, auth_headers, workshop, "Name,Email\nAsha,asha@example.com\n")
    await _import(client, auth_headers, other, "Name,Email\nAsha,asha@example.com\n")
    internship = await _internship(client, auth_headers, scope="institution", institution_id=inst["id"])
    board = await _performance(client, auth_headers, internship)
    assert sorted(s["event_name"] for s in board["students"]) == ["Seminar", "Workshop"]
    assert len({s["student_id"] for s in board["students"]}) == 1  # one person


# ------------------------------------------------------------------- the shortlist


async def test_students_are_selected_shown_as_selected_and_removed(client, auth_headers, db_session, org_id):
    inst, event = await _world(client, auth_headers, db_session, org_id)
    internship = await _internship(client, auth_headers, scope="institution", institution_id=inst["id"], event_id=event["id"])
    ids = await _student_ids(client, auth_headers, internship)

    picked = await client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": [ids["asha@example.com"], ids["meera@example.com"]], "note": "Strong"}, headers=auth_headers)
    assert picked.status_code == 200 and picked.json()["message"].startswith("2 added")
    again = await client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": [ids["asha@example.com"], ids["ravi@example.com"]]}, headers=auth_headers)
    assert "1 added" in again.json()["message"] and "1 already" in again.json()["message"]

    board = await _performance(client, auth_headers, internship)
    assert {s["email"] for s in board["students"] if s["selected"]} == {"asha@example.com", "meera@example.com", "ravi@example.com"}
    alpha = next(t for t in board["teams"] if t["team_name"] == "Alpha")
    assert all(m["selected"] for m in alpha["members"])
    assert (await client.get(f"{_INTERN}/{internship['id']}", headers=auth_headers)).json()["selected_count"] == 3

    selected = (await client.get(f"{_INTERN}/{internship['id']}/selected", headers=auth_headers)).json()
    assert selected["total"] == 3
    asha = next(i for i in selected["items"] if i["email"] == "asha@example.com")
    assert asha["note"] == "Strong" and asha["institution_name"] == "Sri Venkateswara College"
    assert asha["standings"][0]["exam_score"] == 8 and asha["standings"][0]["team"]["team_name"] == "Alpha"

    assert (await client.patch(f"{_INTERN}/{internship['id']}/selected/{ids['asha@example.com']}", json={"note": "Top scorer"}, headers=auth_headers)).status_code == 200
    removed = await client.delete(f"{_INTERN}/{internship['id']}/selected/{ids['ravi@example.com']}", headers=auth_headers)
    assert removed.status_code == 200
    assert (await client.delete(f"{_INTERN}/{internship['id']}/selected/{ids['ravi@example.com']}", headers=auth_headers)).status_code == 404
    after = (await client.get(f"{_INTERN}/{internship['id']}/selected", headers=auth_headers)).json()
    assert after["total"] == 2
    assert next(i for i in after["items"] if i["email"] == "asha@example.com")["note"] == "Top scorer"


async def test_only_students_inside_the_internships_scope_can_be_selected(client, auth_headers):
    inst = await _institution(client, auth_headers)
    workshop = await _event(client, auth_headers, inst, name="Workshop")
    seminar = await _event(client, auth_headers, inst, name="Seminar")
    other_inst = await _institution(client, auth_headers, name="Other College", location="Chennai")
    other_event = await _event(client, auth_headers, other_inst)
    await _import(client, auth_headers, workshop, "Name,Email\nAsha,asha@example.com\n")
    await _import(client, auth_headers, seminar, "Name,Email\nMeera,meera@example.com\n")
    await _import(client, auth_headers, other_event, "Name,Email\nZoya,zoya@example.com\n")

    everyone = await _internship(client, auth_headers, scope="all")
    ids = await _student_ids(client, auth_headers, everyone)
    event_only = await _internship(client, auth_headers, title="Workshop only", scope="institution", institution_id=inst["id"], event_id=workshop["id"])
    college_only = await _internship(client, auth_headers, title="College only", scope="institution", institution_id=inst["id"])

    def select(internship, *emails):
        return client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": [ids[e] for e in emails]}, headers=auth_headers)

    assert (await select(everyone, "asha@example.com", "zoya@example.com")).status_code == 200
    assert (await select(event_only, "asha@example.com")).status_code == 200
    assert (await select(event_only, "meera@example.com")).status_code == 422  # registered for another event
    assert (await select(college_only, "meera@example.com")).status_code == 200
    assert (await select(college_only, "zoya@example.com")).status_code == 422  # another institution
    assert (await select(everyone, "meera@example.com")).status_code == 200
    # a made-up student id is refused too
    r = await client.post(f"{_INTERN}/{everyone['id']}/selected", json={"student_ids": [str(uuid.uuid4())]}, headers=auth_headers)
    assert r.status_code == 422


async def test_deleting_a_student_or_an_internship_clears_the_shortlist_entries(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    await _import(client, auth_headers, event, "Name,Email\nAsha,asha@example.com\nMeera,meera@example.com\n")
    internship = await _internship(client, auth_headers, scope="all")
    ids = await _student_ids(client, auth_headers, internship)
    await client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": list(ids.values())}, headers=auth_headers)
    assert (await client.delete(f"/api/v1/institution-students/{ids['asha@example.com']}", headers=auth_headers)).status_code == 200
    assert (await client.get(f"{_INTERN}/{internship['id']}/selected", headers=auth_headers)).json()["total"] == 1
    assert (await client.delete(f"{_INTERN}/{internship['id']}", headers=auth_headers)).status_code == 200
    assert (await client.get(f"{_INTERN}/{internship['id']}/selected", headers=auth_headers)).status_code == 404


# ------------------------------------------------------------------ access control


async def test_without_the_permission_nothing_is_visible_or_changeable(client, auth_headers, staff_headers):
    internship = await _internship(client, auth_headers)
    for method, url, kwargs in (
        ("get", _INTERN, {}),
        ("post", _INTERN, {"json": {"title": "Another", "scope": "all"}}),
        ("get", f"{_INTERN}/{internship['id']}", {}),
        ("get", f"{_INTERN}/{internship['id']}/performance", {}),
        ("get", f"{_INTERN}/{internship['id']}/selected", {}),
        ("post", f"{_INTERN}/{internship['id']}/selected", {"json": {"student_ids": [str(uuid.uuid4())]}}),
        ("delete", f"{_INTERN}/{internship['id']}", {}),
    ):
        r = await getattr(client, method)(url, headers=staff_headers, **kwargs)
        assert r.status_code == 403, (method, url, r.status_code)


async def test_one_organization_cannot_see_or_touch_anothers_internships(client, auth_headers, db_session):
    internship = await _internship(client, auth_headers)
    other_org = await OrganizationRepository(db_session).create(name="Rival Org", slug=f"rival-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"rival-{uuid.uuid4().hex[:6]}@example.com")
    rival = {"Authorization": f"Bearer {token}"}
    assert (await client.get(_INTERN, headers=rival)).json() == []
    for method, url in (
        ("get", f"{_INTERN}/{internship['id']}"),
        ("get", f"{_INTERN}/{internship['id']}/performance"),
        ("get", f"{_INTERN}/{internship['id']}/selected"),
        ("delete", f"{_INTERN}/{internship['id']}"),
    ):
        assert (await getattr(client, method)(url, headers=rival)).status_code == 404, (method, url)
