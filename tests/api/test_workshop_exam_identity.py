"""
Who an internship exam place belongs to. A place is tied to a selection; an older attendee that only has an e-mail is matched by it only
when exactly ONE selected student of the internship has that address. Two students sharing an address are ambiguous, so access is denied
safely (the attendee, their attempt and result are kept) rather than opening one student's link because the other has access.
Synthetic data only.
"""

import uuid

import pytest
from sqlalchemy import select

from modules.our_internships.models import InternshipSelection, LmsStatus
from modules.workshop_exams.models import WorkshopExamAttendee
from tests.api.test_internship_learning import _EXAMS, _INST, _INTERN, _MINE, _exam, _world
from tests.api.test_learning_integration import _link, _roles  # noqa: F401  (the autouse role fixture)

pytestmark = pytest.mark.api

_PUBLIC = "/api/v1/public/workshop-exams"


async def _open_exam(client, headers, internship):
    exam = await _exam(client, headers, internship)
    await client.post(f"{_EXAMS}/{exam['id']}/questions", json={"questions": [{"text": "2+2?", "options": ["3", "4"], "correct_indices": [1]}]}, headers=headers)
    opened = await client.post(f"{_EXAMS}/{exam['id']}/status", json={"status": "open"}, headers=headers)
    assert opened.status_code == 200, opened.text
    return exam


async def _twin(client, headers, db_session, internship, status: LmsStatus, email="asha@example.com"):
    """A second selected student, from another institution, with the SAME e-mail address (a shared family or college address)."""
    inst = (await client.post(_INST, json={"name": "Other College", "location": "Chennai", "faculty_name": "Dr. M"}, headers=headers)).json()
    event = (await client.post(f"{_INST}/{inst['id']}/events", json={"name": "Workshop 2", "event_type": "workshop", "start_date": "2026-11-10", "end_date": "2026-11-11"}, headers=headers)).json()
    await client.post(f"/api/v1/institution-events/{event['id']}/students/import", data={"text": f"Name,Email,Phone\nAsha Twin,{email},9000022222\n"}, headers=headers)
    board = (await client.get(f"{_INTERN}/{internship['id']}/performance", headers=headers)).json()
    twin = next(s for s in board["students"] if s["email"] == email and s["name"] == "Asha Twin")
    picked = await client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": [twin["student_id"]]}, headers=headers)
    assert picked.status_code == 200, picked.text
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.student_id == uuid.UUID(twin["student_id"])))).scalar_one()
    selection.lms_status = status
    await db_session.flush()
    return selection


async def _legacy_attendee(db_session, exam, email, **over):
    """An attendee from before the selection reference existed: an e-mail and a token, no selection."""
    attendee = WorkshopExamAttendee(exam_id=uuid.UUID(exam["id"]), name="Legacy", email=email, access_token=uuid.uuid4().hex, selection_id=None, **over)
    db_session.add(attendee)
    await db_session.flush()
    return attendee


async def test_an_older_attendee_with_a_unique_email_follows_that_students_access(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    exam = await _open_exam(client, auth_headers, internship)
    attendee = await _legacy_attendee(db_session, exam, "asha@example.com")
    assert (await client.get(f"{_PUBLIC}/{attendee.access_token}")).status_code == 200
    asha = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(people["asha@example.com"][0])))).scalar_one()
    asha.lms_status = LmsStatus.REVOKED
    await db_session.flush()
    assert (await client.get(f"{_PUBLIC}/{attendee.access_token}")).status_code == 404


@pytest.mark.parametrize("twin_status", [LmsStatus.REVOKED, LmsStatus.GRANTED, LmsStatus.NOT_GRANTED])
async def test_an_older_attendee_on_an_address_two_students_share_is_denied_whatever_their_access(client, auth_headers, db_session, organization, twin_status):
    internship, people = await _world(client, auth_headers, db_session, organization)
    await _twin(client, auth_headers, db_session, internship, twin_status)
    exam = await _open_exam(client, auth_headers, internship)
    attendee = await _legacy_attendee(db_session, exam, "asha@example.com")  # Asha (granted) shares the address with her twin
    for call in (client.get(f"{_PUBLIC}/{attendee.access_token}"), client.post(f"{_PUBLIC}/{attendee.access_token}/start"), client.post(f"{_PUBLIC}/{attendee.access_token}/submit", json={"answers": {}})):
        assert (await call).status_code == 404
    # nothing was erased or changed: the attendee and any attempt are still there
    await db_session.refresh(attendee)
    assert attendee.selection_id is None and attendee.email == "asha@example.com"


async def test_a_place_tied_to_a_selection_does_not_depend_on_the_shared_address(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    twin = await _twin(client, auth_headers, db_session, internship, LmsStatus.REVOKED)
    exam = await _open_exam(client, auth_headers, internship)
    asha = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.id == uuid.UUID(people["asha@example.com"][0])))).scalar_one()
    mine = WorkshopExamAttendee(exam_id=uuid.UUID(exam["id"]), name="Asha", email="asha@example.com", access_token=uuid.uuid4().hex, selection_id=asha.id)
    db_session.add(mine)
    await db_session.flush()
    assert (await client.get(f"{_PUBLIC}/{mine.access_token}")).status_code == 200  # her own granted selection opens it
    mine.selection_id = twin.id  # the same place tied to the revoked twin is closed
    await db_session.flush()
    assert (await client.get(f"{_PUBLIC}/{mine.access_token}")).status_code == 404


async def test_a_place_tied_to_a_selection_of_another_internship_is_refused(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    exam = await _open_exam(client, auth_headers, internship)
    other = (await client.post(_INTERN, json={"title": "Other", "scope": "all"}, headers=auth_headers)).json()
    await client.post(f"{_INTERN}/{other['id']}/selected", json={"student_ids": [(await client.get(f"{_INTERN}/{internship['id']}/performance", headers=auth_headers)).json()["students"][0]["student_id"]]}, headers=auth_headers)
    foreign = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.internship_id == uuid.UUID(other["id"])))).scalar_one()
    foreign.lms_status = LmsStatus.GRANTED
    await db_session.flush()
    attendee = WorkshopExamAttendee(exam_id=uuid.UUID(exam["id"]), name="X", email="x@example.com", access_token=uuid.uuid4().hex, selection_id=foreign.id)
    db_session.add(attendee)
    await db_session.flush()
    assert (await client.get(f"{_PUBLIC}/{attendee.access_token}")).status_code == 404  # granted, but on a different internship


async def test_assigning_the_exam_never_guesses_between_students_who_share_an_address(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    await _twin(client, auth_headers, db_session, internship, LmsStatus.GRANTED)  # two granted students, one address
    exam = await _open_exam(client, auth_headers, internship)
    result = (await client.post(f"{_INTERN}/{internship['id']}/exams/{exam['id']}/assign", json={"send_invites": False}, headers=auth_headers)).json()
    assert result == {"added": 1, "already_on_exam": 0, "invited": 0, "skipped_shared_email": 2}  # only Meera (unique address) got a place
    emails = (await db_session.execute(select(WorkshopExamAttendee.email).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalars().all()
    assert emails == ["meera@example.com"]


async def test_a_student_never_sees_a_link_that_only_matches_a_shared_address_and_results_do_not_credit_either_student(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    await _link(db_session, organization, internship)
    await _twin(client, auth_headers, db_session, internship, LmsStatus.GRANTED)
    exam = await _open_exam(client, auth_headers, internship)
    legacy = await _legacy_attendee(db_session, exam, "asha@example.com")
    legacy.submitted_at = legacy.started_at = legacy.created_at
    legacy.score, legacy.total_marks = 1, 1
    await db_session.flush()
    asha_headers = people["asha@example.com"][1]
    assert legacy.access_token not in (await client.get(f"{_MINE}/{internship['id']}/exams", headers=asha_headers)).text
    rows = (await client.get(f"{_INTERN}/{internship['id']}/exams/{exam['id']}/results", headers=auth_headers)).json()
    asha_rows = [r for r in rows if r["student_email"] == "asha@example.com"]
    assert len(asha_rows) == 2 and all(r["state"] == "not_assigned" and r["score"] is None for r in asha_rows)  # the result is kept, credited to nobody
    await db_session.refresh(legacy)
    assert legacy.score == 1  # still on record


async def test_an_unambiguous_legacy_attendee_is_linked_when_the_exam_is_assigned(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    exam = await _open_exam(client, auth_headers, internship)
    legacy = await _legacy_attendee(db_session, exam, "meera@example.com")
    result = (await client.post(f"{_INTERN}/{internship['id']}/exams/{exam['id']}/assign", json={"send_invites": False}, headers=auth_headers)).json()
    assert result["already_on_exam"] == 1 and result["added"] == 1
    await db_session.refresh(legacy)
    assert legacy.selection_id == uuid.UUID(people["meera@example.com"][0])
