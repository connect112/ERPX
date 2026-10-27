"""
Institutions, their events, the students registered for them, and the exams and hackathons linked to an event.

The rules worth pinning: a list uploaded to one event registers people for that event only; the same person is one
record however many lists they appear on; an exam or hackathon is one record that belongs to at most one event; and
everything is scoped to the caller's organization and to the institutions.view / institutions.manage permissions.
"""

import io
import uuid

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from modules.hackathons.models import Hackathon
from modules.organizations.repository import OrganizationRepository
from modules.workshop_exams.models import WorkshopExam
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_BASE = "/api/v1/institutions"
_EVENTS = "/api/v1/institution-events"
_STUDENTS = "/api/v1/institution-students"


def _institution_body(**over):
    return {
        "name": "Sri Venkateswara College",
        "location": "Tirupati",
        "faculty_name": "Dr. Lakshmi",
        "faculty_email": "lakshmi@svc.example.com",
        "faculty_phone": "9876500000",
        "faculty_designation": "Head of CSE",
        "mou_details": "Signed 12 Sep 2026, valid 2 years",
        **over,
    }


def _event_body(**over):
    return {"name": "Cyber Workshop", "event_type": "workshop", "start_date": "2026-11-10", "end_date": "2026-11-11", **over}


async def _institution(client, headers, **over):
    r = await client.post(_BASE, json=_institution_body(**over), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _event(client, headers, institution, **over):
    r = await client.post(f"{_BASE}/{institution['id']}/events", json=_event_body(**over), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _import(client, headers, event, text, dry_run=False):
    r = await client.post(
        f"{_EVENTS}/{event['id']}/students/import", data={"text": text, "dry_run": str(dry_run).lower()}, headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _students(client, headers, event):
    r = await client.get(f"{_EVENTS}/{event['id']}/students", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


_LIST = "Name,Email,Phone\nAsha Rao,asha@example.com,9876543210\nMeera Iyer,meera@example.com,9123456789\n"


# --------------------------------------------------------------- institutions


async def test_an_institution_is_created_with_its_faculty_contact_and_listed_with_counts(client, auth_headers):
    created = await _institution(client, auth_headers)
    assert created["name"] == "Sri Venkateswara College"
    assert created["faculty_name"] == "Dr. Lakshmi"
    assert created["event_count"] == 0 and created["student_count"] == 0
    await _event(client, auth_headers, created)
    listed = (await client.get(_BASE, headers=auth_headers)).json()
    assert listed["total"] == 1
    assert listed["items"][0]["event_count"] == 1


async def test_name_location_and_faculty_name_are_required_and_a_bad_email_is_refused(client, auth_headers):
    for body in (
        {**_institution_body(), "location": ""},
        {**_institution_body(), "faculty_name": ""},
        {**_institution_body(), "faculty_email": "not-an-email"},
    ):
        assert (await client.post(_BASE, json=body, headers=auth_headers)).status_code == 422
    # everything else is optional
    minimal = {"name": "Small College", "location": "Nellore", "faculty_name": "Prof. Rao"}
    assert (await client.post(_BASE, json=minimal, headers=auth_headers)).status_code == 201


async def test_the_same_name_in_the_same_place_is_a_duplicate_but_another_city_is_fine(client, auth_headers):
    await _institution(client, auth_headers)
    again = await client.post(_BASE, json=_institution_body(name="SRI VENKATESWARA COLLEGE", location="tirupati"), headers=auth_headers)
    assert again.status_code == 409
    assert (await client.post(_BASE, json=_institution_body(location="Hyderabad"), headers=auth_headers)).status_code == 201


async def test_institutions_can_be_searched_updated_and_deleted(client, auth_headers):
    a = await _institution(client, auth_headers)
    await _institution(client, auth_headers, name="Godavari Institute", location="Rajahmundry", faculty_name="Dr. Sita")
    found = (await client.get(_BASE, params={"q": "godavari"}, headers=auth_headers)).json()
    assert [i["name"] for i in found["items"]] == ["Godavari Institute"]
    by_faculty = (await client.get(_BASE, params={"q": "lakshmi"}, headers=auth_headers)).json()
    assert by_faculty["total"] == 1

    patched = await client.patch(f"{_BASE}/{a['id']}", json={"faculty_phone": "9000000000", "notes": "Prefers Tuesdays"}, headers=auth_headers)
    assert patched.status_code == 200 and patched.json()["notes"] == "Prefers Tuesdays"
    assert (await client.patch(f"{_BASE}/{a['id']}", json={"name": None}, headers=auth_headers)).status_code == 422
    assert (await client.patch(f"{_BASE}/{a['id']}", json={"name": "Godavari Institute", "location": "Rajahmundry"}, headers=auth_headers)).status_code == 409

    assert (await client.delete(f"{_BASE}/{a['id']}", headers=auth_headers)).status_code == 200
    assert (await client.get(f"{_BASE}/{a['id']}", headers=auth_headers)).status_code == 404


async def test_the_mou_document_can_be_uploaded_downloaded_and_removed(client, auth_headers):
    inst = await _institution(client, auth_headers)
    pdf = b"%PDF-1.4 test mou"
    up = await client.put(f"{_BASE}/{inst['id']}/mou", files={"file": ("mou.pdf", pdf, "application/pdf")}, headers=auth_headers)
    assert up.status_code == 200, up.text
    assert up.json()["mou_filename"] == "mou.pdf" and up.json()["mou_size_bytes"] == len(pdf)
    down = await client.get(f"{_BASE}/{inst['id']}/mou", headers=auth_headers)
    assert down.status_code == 200 and down.content == pdf
    assert down.headers["x-content-type-options"] == "nosniff"
    # the MOU bytes are never part of the institution JSON
    assert "mou_data" not in (await client.get(f"{_BASE}/{inst['id']}", headers=auth_headers)).json()
    bad = await client.put(f"{_BASE}/{inst['id']}/mou", files={"file": ("x.exe", b"MZ", "application/octet-stream")}, headers=auth_headers)
    assert bad.status_code == 422
    gone = await client.delete(f"{_BASE}/{inst['id']}/mou", headers=auth_headers)
    assert gone.json()["mou_filename"] is None
    assert (await client.get(f"{_BASE}/{inst['id']}/mou", headers=auth_headers)).status_code == 404


# --------------------------------------------------------------------- events


async def test_an_event_has_dates_a_type_an_optional_capacity_and_a_status(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst, event_type="hackathon", max_capacity=120, description="Day 3")
    assert event["status"] == "upcoming" and event["event_type"] == "hackathon" and event["max_capacity"] == 120
    assert event["institution_name"] == "Sri Venkateswara College"
    bad_dates = await client.post(f"{_BASE}/{inst['id']}/events", json=_event_body(end_date="2026-11-09"), headers=auth_headers)
    assert bad_dates.status_code == 422
    moved = await client.patch(f"{_EVENTS}/{event['id']}", json={"status": "ongoing"}, headers=auth_headers)
    assert moved.json()["status"] == "ongoing"
    done = await client.patch(f"{_EVENTS}/{event['id']}", json={"status": "completed", "max_capacity": None}, headers=auth_headers)
    assert done.json()["status"] == "completed" and done.json()["max_capacity"] is None
    assert (await client.patch(f"{_EVENTS}/{event['id']}", json={"end_date": "2026-01-01"}, headers=auth_headers)).status_code == 422
    listed = (await client.get(f"{_BASE}/{inst['id']}/events", headers=auth_headers)).json()
    assert [e["id"] for e in listed] == [event["id"]]


# ------------------------------------------------------------ student import


async def test_uploading_a_list_to_an_event_registers_those_people_for_that_event_only(client, auth_headers):
    college_a = await _institution(client, auth_headers)
    college_b = await _institution(client, auth_headers, name="Other College", location="Chennai", faculty_name="Dr. B")
    workshop = await _event(client, auth_headers, college_a, name="Workshop")
    hackathon = await _event(client, auth_headers, college_a, name="Hackathon", event_type="hackathon")
    elsewhere = await _event(client, auth_headers, college_b, name="Their workshop")

    result = await _import(client, auth_headers, workshop, _LIST)
    assert (result["new_students"], result["registered"], result["problems"]) == (2, 2, [])

    assert (await _students(client, auth_headers, workshop))["total"] == 2
    # not in the hackathon at the same college, nor at the other college's event
    assert (await _students(client, auth_headers, hackathon))["total"] == 0
    assert (await _students(client, auth_headers, elsewhere))["total"] == 0
    # they are at the institution though, and the directory says which event they are in
    directory = (await client.get(f"{_BASE}/{college_a['id']}/students", headers=auth_headers)).json()
    assert directory["total"] == 2
    assert {e["event_name"] for s in directory["items"] for e in s["events"]} == {"Workshop"}
    assert (await client.get(f"{_BASE}/{college_b['id']}/students", headers=auth_headers)).json()["total"] == 0


async def test_the_same_person_on_a_second_event_is_one_student_not_two(client, auth_headers):
    inst = await _institution(client, auth_headers)
    workshop = await _event(client, auth_headers, inst, name="Workshop")
    hackathon = await _event(client, auth_headers, inst, name="Hackathon", event_type="hackathon")
    await _import(client, auth_headers, workshop, _LIST)
    second = await _import(client, auth_headers, hackathon, "Name,Email\nASHA RAO,Asha@Example.com\nNew Person,new@example.com\n")
    assert (second["existing_students"], second["new_students"], second["registered"]) == (1, 1, 2)
    directory = (await client.get(f"{_BASE}/{inst['id']}/students", headers=auth_headers)).json()
    assert directory["total"] == 3
    asha = next(s for s in directory["items"] if s["email"] == "asha@example.com")
    assert asha["name"] == "Asha Rao"  # an import never renames someone who is already there
    assert {e["event_name"] for e in asha["events"]} == {"Workshop", "Hackathon"}


async def test_uploading_the_same_list_twice_adds_nobody_new(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    await _import(client, auth_headers, event, _LIST)
    again = await _import(client, auth_headers, event, _LIST)
    assert (again["new_students"], again["registered"], again["already_registered"]) == (0, 0, 2)
    assert (await _students(client, auth_headers, event))["total"] == 2


async def test_a_dry_run_reports_what_would_happen_and_writes_nothing(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    preview = await _import(client, auth_headers, event, _LIST + "Bad Row,nope\n", dry_run=True)
    assert preview["dry_run"] is True
    assert (preview["new_students"], preview["registered"]) == (2, 2)
    assert [p["row"] for p in preview["problems"]] == [4]
    assert (await _students(client, auth_headers, event))["total"] == 0
    assert (await client.get(f"{_BASE}/{inst['id']}/students", headers=auth_headers)).json()["total"] == 0


async def test_unusable_rows_and_duplicates_in_the_file_are_reported_and_the_rest_import(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    text = "Name,Email\nAsha,asha@example.com\nNo Email,\nAsha Again,ASHA@example.com\nMeera,meera@example.com\n"
    result = await _import(client, auth_headers, event, text)
    assert result["registered"] == 2
    reasons = {p["row"]: p["reason"] for p in result["problems"]}
    assert reasons[3] == "No email address."
    assert "Same email as row 2" in reasons[4]


async def test_the_event_capacity_is_enforced_and_the_overflow_is_reported(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst, max_capacity=2)
    text = "Name,Email\nA,a@example.com\nB,b@example.com\nC,c@example.com\n"
    result = await _import(client, auth_headers, event, text)
    assert (result["registered"], result["over_capacity"]) == (2, 1)
    assert "full" in result["problems"][0]["reason"]
    assert (await _students(client, auth_headers, event))["total"] == 2
    # the limit cannot be set below what is already registered
    assert (await client.patch(f"{_EVENTS}/{event['id']}", json={"max_capacity": 1}, headers=auth_headers)).status_code == 422


async def test_an_excel_file_can_be_uploaded(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    book = Workbook()
    sheet = book.active
    sheet.append(["Student Name", "Email ID", "Mobile", "Department"])
    sheet.append(["Asha Rao", "asha@example.com", 9876543210, "CSE"])
    out = io.BytesIO()
    book.save(out)
    r = await client.post(
        f"{_EVENTS}/{event['id']}/students/import",
        files={"file": ("students.xlsx", out.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["registered"] == 1
    student = (await _students(client, auth_headers, event))["items"][0]
    assert student["phone"] == "9876543210" and student["details"] == {"Department": "CSE"}


async def test_a_list_that_cannot_be_read_is_a_clear_422_not_a_crash(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    for files, data in (
        ({"file": ("notes.docx", b"x", "application/octet-stream")}, None),
        ({"file": ("old.xls", b"x", "application/octet-stream")}, None),
        (None, {"text": "   "}),
        (None, None),
    ):
        r = await client.post(f"{_EVENTS}/{event['id']}/students/import", files=files, data=data, headers=auth_headers)
        assert r.status_code == 422, (files, data, r.text)


# ----------------------------------------------------- student directory


async def test_students_can_be_searched_opened_and_corrected(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    await _import(client, auth_headers, event, _LIST)
    found = (await client.get(f"{_EVENTS}/{event['id']}/students", params={"q": "meera"}, headers=auth_headers)).json()
    assert [s["name"] for s in found["items"]] == ["Meera Iyer"]
    # a wildcard typed in the search box is text, not a pattern
    assert (await client.get(f"{_EVENTS}/{event['id']}/students", params={"q": "%"}, headers=auth_headers)).json()["total"] == 0

    sid = found["items"][0]["student_id"]
    profile = (await client.get(f"{_STUDENTS}/{sid}", headers=auth_headers)).json()
    assert profile["institution_name"] == "Sri Venkateswara College"
    assert [e["event_name"] for e in profile["events"]] == ["Cyber Workshop"]

    fixed = await client.patch(
        f"{_STUDENTS}/{sid}", json={"name": "Meera  Iyer-Rao", "email": "Meera.Rao@Example.com", "phone": "9000011111"}, headers=auth_headers
    )
    assert fixed.status_code == 200, fixed.text
    assert (fixed.json()["name"], fixed.json()["email"]) == ("Meera Iyer-Rao", "meera.rao@example.com")
    # the correction shows in the event's list too (same record)
    emails = {x["email"] for x in (await _students(client, auth_headers, event))["items"]}
    assert "meera.rao@example.com" in emails and "meera@example.com" not in emails
    clash = await client.patch(f"{_STUDENTS}/{sid}", json={"email": "asha@example.com"}, headers=auth_headers)
    assert clash.status_code == 409


async def test_a_student_can_be_added_by_hand_registered_later_and_removed_from_an_event(client, auth_headers):
    inst = await _institution(client, auth_headers)
    first = await _event(client, auth_headers, inst, name="First")
    second = await _event(client, auth_headers, inst, name="Second")
    added = await client.post(
        f"{_BASE}/{inst['id']}/students", params={"event_id": first["id"]},
        json={"name": "Ravi Kumar", "email": "ravi@example.com", "details": {"Year": "3"}}, headers=auth_headers,
    )
    assert added.status_code == 201, added.text
    sid = added.json()["id"]
    assert [e["event_name"] for e in added.json()["events"]] == ["First"]
    dup = await client.post(f"{_BASE}/{inst['id']}/students", json={"name": "Ravi", "email": "RAVI@example.com"}, headers=auth_headers)
    assert dup.status_code == 409

    reg = await client.post(f"{_EVENTS}/{second['id']}/students", json={"student_ids": [sid]}, headers=auth_headers)
    assert reg.status_code == 200 and "1 registered" in reg.json()["message"]
    assert (await _students(client, auth_headers, second))["total"] == 1

    # removing from one event leaves the other, and the student at the institution
    assert (await client.delete(f"{_EVENTS}/{first['id']}/students/{sid}", headers=auth_headers)).status_code == 200
    assert (await _students(client, auth_headers, first))["total"] == 0
    assert (await _students(client, auth_headers, second))["total"] == 1
    assert (await client.get(f"{_STUDENTS}/{sid}", headers=auth_headers)).status_code == 200
    # ...and deleting the student removes them everywhere
    assert (await client.delete(f"{_STUDENTS}/{sid}", headers=auth_headers)).status_code == 200
    assert (await _students(client, auth_headers, second))["total"] == 0


async def test_only_students_of_the_same_institution_can_be_registered_for_an_event(client, auth_headers):
    mine = await _institution(client, auth_headers)
    theirs = await _institution(client, auth_headers, name="Other College", location="Chennai", faculty_name="Dr. B")
    event = await _event(client, auth_headers, mine)
    stranger = (
        await client.post(f"{_BASE}/{theirs['id']}/students", json={"name": "Stranger", "email": "s@example.com"}, headers=auth_headers)
    ).json()
    r = await client.post(f"{_EVENTS}/{event['id']}/students", json={"student_ids": [stranger["id"]]}, headers=auth_headers)
    assert r.status_code == 422
    wrong_event = await client.post(
        f"{_BASE}/{theirs['id']}/students", params={"event_id": event["id"]}, json={"name": "X", "email": "x@example.com"}, headers=auth_headers
    )
    assert wrong_event.status_code == 422


async def test_an_individual_score_and_remarks_are_kept_per_event(client, auth_headers):
    inst = await _institution(client, auth_headers)
    workshop = await _event(client, auth_headers, inst, name="Workshop")
    hackathon = await _event(client, auth_headers, inst, name="Hackathon")
    await _import(client, auth_headers, workshop, _LIST)
    await _import(client, auth_headers, hackathon, "Name,Email\nAsha Rao,asha@example.com\n")
    sid = next(s for s in (await _students(client, auth_headers, workshop))["items"] if s["email"] == "asha@example.com")["student_id"]
    saved = await client.patch(f"{_EVENTS}/{hackathon['id']}/students/{sid}", json={"individual_score": 8.5, "remarks": "Led the team"}, headers=auth_headers)
    assert saved.status_code == 200
    in_hackathon = (await _students(client, auth_headers, hackathon))["items"][0]
    assert (in_hackathon["individual_score"], in_hackathon["remarks"]) == (8.5, "Led the team")
    in_workshop = next(s for s in (await _students(client, auth_headers, workshop))["items"] if s["email"] == "asha@example.com")
    assert in_workshop["individual_score"] is None
    assert (await client.patch(f"{_EVENTS}/{hackathon['id']}/students/{sid}", json={"individual_score": -1}, headers=auth_headers)).status_code == 422
    stranger = await client.patch(f"{_EVENTS}/{hackathon['id']}/students/{uuid.uuid4()}", json={"individual_score": 1}, headers=auth_headers)
    assert stranger.status_code == 404


# --------------------------------------------- exams and hackathons of an event


async def _make_exam(client, headers, **over):
    r = await client.post("/api/v1/workshop-exams", json={"title": "Workshop MCQ", "duration_minutes": 30, **over}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _hackathon_body(**over):
    return {
        "code": f"HK-{uuid.uuid4().hex[:6]}",
        "title": "Day 3 Hackathon",
        "registration_deadline": "2026-11-09",
        "start_date": "2026-11-12",
        "end_date": "2026-11-12",
        **over,
    }


async def test_an_existing_exam_can_be_linked_to_an_event_and_is_the_same_record(client, auth_headers, db_session):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _make_exam(client, auth_headers)
    candidates = (await client.get(f"{_EVENTS}/{event['id']}/exam-candidates", headers=auth_headers)).json()
    assert [c["id"] for c in candidates] == [exam["id"]]

    assert (await client.put(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)).status_code == 200
    linked = (await client.get(f"{_EVENTS}/{event['id']}/exams", headers=auth_headers)).json()
    assert [e["id"] for e in linked] == [exam["id"]]
    # no longer on offer anywhere, and still the one exam in the Workshop Exams module
    assert (await client.get(f"{_EVENTS}/{event['id']}/exam-candidates", headers=auth_headers)).json() == []
    in_module = (await client.get("/api/v1/workshop-exams", headers=auth_headers)).json()
    assert [e["id"] for e in in_module] == [exam["id"]] and in_module[0]["event_id"] == event["id"]
    assert (await _event(client, auth_headers, inst, name="Another"))["exam_count"] == 0

    other = await _event(client, auth_headers, inst, name="Another event")
    assert (await client.put(f"{_EVENTS}/{other['id']}/exams/{exam['id']}", headers=auth_headers)).status_code == 409

    assert (await client.delete(f"{_EVENTS}/{event['id']}/exams/{exam['id']}", headers=auth_headers)).status_code == 200
    row = (await db_session.execute(select(WorkshopExam).where(WorkshopExam.id == uuid.UUID(exam["id"])))).scalar_one()
    assert row.event_id is None  # unlinked, not deleted


async def test_an_exam_can_be_created_from_the_event_and_is_in_both_places(client, auth_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _make_exam(client, auth_headers, event_id=event["id"])
    assert exam["event_id"] == event["id"]
    assert [e["id"] for e in (await client.get(f"{_EVENTS}/{event['id']}/exams", headers=auth_headers)).json()] == [exam["id"]]
    assert exam["id"] in [e["id"] for e in (await client.get("/api/v1/workshop-exams", headers=auth_headers)).json()]
    counts = (await client.get(f"{_EVENTS}/{event['id']}", headers=auth_headers)).json()
    assert counts["exam_count"] == 1
    # an event that is not yours (or does not exist) cannot be used
    assert (await client.post("/api/v1/workshop-exams", json={"title": "Exam for nowhere", "event_id": str(uuid.uuid4())}, headers=auth_headers)).status_code == 404


async def test_a_hackathon_can_be_linked_or_created_from_the_event(client, auth_headers, db_session):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst, event_type="hackathon")
    existing = (await client.post("/api/v1/hackathons", json=_hackathon_body(), headers=auth_headers)).json()
    assert [h["id"] for h in (await client.get(f"{_EVENTS}/{event['id']}/hackathon-candidates", headers=auth_headers)).json()] == [existing["id"]]
    assert (await client.put(f"{_EVENTS}/{event['id']}/hackathons/{existing['id']}", headers=auth_headers)).status_code == 200

    created = await client.post("/api/v1/hackathons", json=_hackathon_body(event_id=event["id"]), headers=auth_headers)
    assert created.status_code == 201 and created.json()["event_id"] == event["id"]
    listed = (await client.get(f"{_EVENTS}/{event['id']}/hackathons", headers=auth_headers)).json()
    assert {h["id"] for h in listed} == {existing["id"], created.json()["id"]}
    assert (await client.get(f"{_EVENTS}/{event['id']}", headers=auth_headers)).json()["hackathon_count"] == 2
    assert (await client.post("/api/v1/hackathons", json=_hackathon_body(event_id=str(uuid.uuid4())), headers=auth_headers)).status_code == 404

    assert (await client.delete(f"{_EVENTS}/{event['id']}/hackathons/{existing['id']}", headers=auth_headers)).status_code == 200
    row = (await db_session.execute(select(Hackathon).where(Hackathon.id == uuid.UUID(existing["id"])))).scalar_one()
    assert row.event_id is None


async def test_deleting_an_event_keeps_its_exams_and_hackathons(client, auth_headers, db_session):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    exam = await _make_exam(client, auth_headers, event_id=event["id"])
    hackathon = (await client.post("/api/v1/hackathons", json=_hackathon_body(event_id=event["id"]), headers=auth_headers)).json()
    assert (await client.delete(f"{_EVENTS}/{event['id']}", headers=auth_headers)).status_code == 200
    db_session.expire_all()
    assert (await db_session.execute(select(WorkshopExam.event_id).where(WorkshopExam.id == uuid.UUID(exam["id"])))).scalar_one() is None
    assert (await db_session.execute(select(Hackathon.event_id).where(Hackathon.id == uuid.UUID(hackathon["id"])))).scalar_one() is None


# ------------------------------------------------------ access control


async def test_without_the_permission_nothing_is_visible_or_changeable(client, auth_headers, staff_headers):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    for method, url, kwargs in (
        ("get", _BASE, {}),
        ("post", _BASE, {"json": _institution_body(name="Another")}),
        ("get", f"{_BASE}/{inst['id']}", {}),
        ("get", f"{_BASE}/{inst['id']}/students", {}),
        ("post", f"{_EVENTS}/{event['id']}/students/import", {"data": {"text": _LIST}}),
        ("get", f"{_EVENTS}/{event['id']}/exams", {}),
        ("delete", f"{_BASE}/{inst['id']}", {}),
    ):
        r = await getattr(client, method)(url, headers=staff_headers, **kwargs)
        assert r.status_code == 403, (method, url, r.status_code)


async def test_one_organization_cannot_see_or_touch_anothers_institutions(client, auth_headers, db_session):
    inst = await _institution(client, auth_headers)
    event = await _event(client, auth_headers, inst)
    await _import(client, auth_headers, event, _LIST)
    sid = (await _students(client, auth_headers, event))["items"][0]["student_id"]

    other_org = await OrganizationRepository(db_session).create(name="Rival Org", slug=f"rival-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"rival-{uuid.uuid4().hex[:6]}@example.com")
    rival = {"Authorization": f"Bearer {token}"}

    assert (await client.get(_BASE, headers=rival)).json()["total"] == 0
    for method, url in (
        ("get", f"{_BASE}/{inst['id']}"),
        ("get", f"{_BASE}/{inst['id']}/events"),
        ("get", f"{_BASE}/{inst['id']}/students"),
        ("get", f"{_EVENTS}/{event['id']}"),
        ("get", f"{_EVENTS}/{event['id']}/students"),
        ("get", f"{_STUDENTS}/{sid}"),
        ("delete", f"{_BASE}/{inst['id']}"),
    ):
        assert (await getattr(client, method)(url, headers=rival)).status_code == 404, (method, url)
    assert (await client.patch(f"{_STUDENTS}/{sid}", json={"name": "Hijack"}, headers=rival)).status_code == 404
    still = (await _students(client, auth_headers, event))["items"][0]
    assert still["name"] != "Hijack"
