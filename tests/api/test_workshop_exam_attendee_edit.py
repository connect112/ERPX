"""
Exam admin: correct an attendee's name and email, delete a submission so they can sit the exam again, and
remove an attendee (which also cancels any certificate issued to them).
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from modules.workshop_exams.models import WorkshopExamAttendee

pytestmark = pytest.mark.api

_BASE = "/api/v1/workshop-exams"
_PUBLIC = "/api/v1/public/workshop-exams"

_QUESTIONS = [
    {"text": "2 + 2?", "options": ["3", "4", "5"], "correct_indices": [1], "marks": 1},
    {"text": "Capital of France?", "options": ["Paris", "Rome"], "correct_indices": [0], "marks": 2},
]


async def _exam(client, auth_headers, attendees=None):
    created = await client.post(_BASE, json={"title": "Workshop MCQ", "duration_minutes": 30}, headers=auth_headers)
    assert created.status_code == 201, created.text
    exam = created.json()
    await client.post(f"{_BASE}/{exam['id']}/questions", json={"questions": _QUESTIONS}, headers=auth_headers)
    rows = attendees or [
        {"name": "Asha Rao", "email": "asha@example.com"},
        {"name": "Ravi Kumar", "email": "ravi@example.com"},
    ]
    await client.post(f"{_BASE}/{exam['id']}/attendees", json={"attendees": rows}, headers=auth_headers)
    opened = await client.post(f"{_BASE}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    assert opened.status_code == 200, opened.text
    return exam


async def _attendees(client, auth_headers, exam):
    r = await client.get(f"{_BASE}/{exam['id']}/attendees", headers=auth_headers)
    return {a["email"]: a for a in r.json()}


async def _token(db_session, attendee_id):
    row = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.id == uuid.UUID(attendee_id)))).scalar_one()
    return row.access_token


async def _sit(client, token):
    start = (await client.post(f"{_PUBLIC}/{token}/start")).json()
    answers = {q["id"]: [1] if q["text"] == "2 + 2?" else [0] for q in start["questions"]}
    submitted = await client.post(f"{_PUBLIC}/{token}/submit", json={"answers": answers})
    assert submitted.status_code == 200, submitted.text


async def test_name_and_email_can_be_corrected_and_the_personal_link_stays_the_same(client, auth_headers, db_session):
    exam = await _exam(client, auth_headers)
    asha = (await _attendees(client, auth_headers, exam))["asha@example.com"]
    token = await _token(db_session, asha["id"])
    url = f"{_BASE}/{exam['id']}/attendees/{asha['id']}"

    fixed = await client.patch(url, json={"name": "  Asha   Rao-Iyer ", "email": "Asha.New@Example.com"}, headers=auth_headers)
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["name"] == "Asha Rao-Iyer" and fixed.json()["email"] == "asha.new@example.com"
    listed = await _attendees(client, auth_headers, exam)
    assert "asha@example.com" not in listed and listed["asha.new@example.com"]["id"] == asha["id"]
    # Their link is unchanged and now greets them by the corrected name.
    info = (await client.get(f"{_PUBLIC}/{token}")).json()
    assert info["attendee_name"] == "Asha Rao-Iyer" and info["state"] == "ready"

    # Only the name, or only the email, can be sent; the email can't be one a classmate already has.
    assert (await client.patch(url, json={"name": "Asha R"}, headers=auth_headers)).json()["email"] == "asha.new@example.com"
    clash = await client.patch(url, json={"email": "ravi@example.com"}, headers=auth_headers)
    assert clash.status_code == 409 and "already uses" in clash.text
    same = await client.patch(url, json={"email": "ASHA.NEW@example.com"}, headers=auth_headers)
    assert same.status_code == 200  # their own address, in another case, is not a clash
    for bad in ({"name": "   "}, {"email": "not-an-email"}):
        assert (await client.patch(url, json=bad, headers=auth_headers)).status_code == 422, bad
    # An attendee of another exam can't be reached through this one.
    other = await _exam(client, auth_headers, attendees=[{"name": "Kiran P", "email": "kiran@example.com"}])
    kiran = (await _attendees(client, auth_headers, other))["kiran@example.com"]
    assert (await client.patch(f"{_BASE}/{exam['id']}/attendees/{kiran['id']}", json={"name": "X"}, headers=auth_headers)).status_code == 404
    assert (await client.patch(f"{_BASE}/{exam['id']}/attendees/{uuid.uuid4()}", json={"name": "X"}, headers=auth_headers)).status_code == 404


async def test_the_exam_link_can_be_emailed_to_a_corrected_address(client, auth_headers, db_session, monkeypatch):
    from modules.workshop_exams import routes

    queued: list[uuid.UUID] = []
    monkeypatch.setattr(routes, "enqueue_invite_best_effort", lambda attendee_id: queued.append(attendee_id))
    exam = await _exam(client, auth_headers)
    people = await _attendees(client, auth_headers, exam)
    asha, ravi = people["asha@example.com"], people["ravi@example.com"]

    # Asked for, address changed, still has the exam to sit: the link goes to the new address.
    await client.patch(f"{_BASE}/{exam['id']}/attendees/{asha['id']}", json={"email": "asha.new@example.com", "send_link": True}, headers=auth_headers)
    assert queued == [uuid.UUID(asha["id"])]
    assert (await _attendees(client, auth_headers, exam))["asha.new@example.com"]["invited_at"] is not None
    # Not asked for, or address unchanged: nothing is sent.
    await client.patch(f"{_BASE}/{exam['id']}/attendees/{ravi['id']}", json={"email": "ravi.new@example.com"}, headers=auth_headers)
    await client.patch(f"{_BASE}/{exam['id']}/attendees/{ravi['id']}", json={"name": "Ravi K", "send_link": True}, headers=auth_headers)
    assert queued == [uuid.UUID(asha["id"])]
    # Someone who already submitted has nothing left to sit, so no link.
    await _sit(client, await _token(db_session, ravi["id"]))
    await client.patch(f"{_BASE}/{exam['id']}/attendees/{ravi['id']}", json={"email": "ravi.again@example.com", "send_link": True}, headers=auth_headers)
    assert queued == [uuid.UUID(asha["id"])]


async def test_deleting_a_submission_lets_the_person_sit_the_exam_again(client, auth_headers, db_session):
    exam = await _exam(client, auth_headers)
    asha = (await _attendees(client, auth_headers, exam))["asha@example.com"]
    token = await _token(db_session, asha["id"])
    await _sit(client, token)
    dash = (await client.get(f"{_BASE}/{exam['id']}/dashboard", headers=auth_headers)).json()
    assert dash["submitted"] == 1
    assert (await client.get(f"{_PUBLIC}/{token}")).json()["state"] == "submitted"

    url = f"{_BASE}/{exam['id']}/attendees/{asha['id']}"
    reset = await client.post(f"{url}/reset-submission", headers=auth_headers)
    assert reset.status_code == 200 and "sit the exam again" in reset.json()["message"]
    again = (await _attendees(client, auth_headers, exam))["asha@example.com"]
    assert again["id"] == asha["id"] and again["submitted_at"] is None and again["started_at"] is None and again["score"] is None
    assert (await client.get(f"{_BASE}/{exam['id']}/dashboard", headers=auth_headers)).json()["submitted"] == 0
    assert (await client.get(f"{_PUBLIC}/{token}")).json()["state"] == "ready"  # the same link works again
    await _sit(client, token)  # and they can complete it again
    assert (await client.get(f"{_PUBLIC}/{token}")).json()["state"] == "submitted"


async def test_a_certificate_that_was_not_sent_yet_is_cancelled_with_the_submission_but_a_sent_one_blocks_it(client, auth_headers, db_session):
    exam = await _exam(client, auth_headers)
    people = await _attendees(client, auth_headers, exam)
    asha, ravi = people["asha@example.com"], people["ravi@example.com"]
    for person in (asha, ravi):
        await _sit(client, await _token(db_session, person["id"]))
    await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)
    rows = {a.email: a for a in (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalars()}
    assert rows["asha@example.com"].certificate_number and rows["ravi@example.com"].certificate_number
    rows["ravi@example.com"].certificate_sent_at = datetime.now(timezone.utc)  # Ravi's has gone out
    await db_session.flush()

    # Asha's was only queued: deleting her submission cancels it.
    ok = await client.post(f"{_BASE}/{exam['id']}/attendees/{asha['id']}/reset-submission", headers=auth_headers)
    assert ok.status_code == 200
    await db_session.refresh(rows["asha@example.com"])
    assert rows["asha@example.com"].certificate_number is None
    # Ravi's has been delivered, so it must be cancelled by removing him instead.
    blocked = await client.post(f"{_BASE}/{exam['id']}/attendees/{ravi['id']}/reset-submission", headers=auth_headers)
    assert blocked.status_code == 409 and "already been sent" in blocked.text
    assert (await _attendees(client, auth_headers, exam))["ravi@example.com"]["submitted_at"] is not None


async def test_removing_an_attendee_deletes_them_and_cancels_their_certificate(client, auth_headers, db_session):
    exam = await _exam(client, auth_headers)
    asha = (await _attendees(client, auth_headers, exam))["asha@example.com"]
    token = await _token(db_session, asha["id"])
    await _sit(client, token)
    await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)
    number = (await _attendees(client, auth_headers, exam))["asha@example.com"]["certificate_number"]
    assert (await client.get(f"/api/v1/public/workshop-certificates/verify/{number}")).json()["valid"] is True

    gone = await client.delete(f"{_BASE}/{exam['id']}/attendees/{asha['id']}", headers=auth_headers)
    assert gone.status_code == 200
    assert "asha@example.com" not in await _attendees(client, auth_headers, exam)
    assert (await client.get(f"{_BASE}/{exam['id']}/dashboard", headers=auth_headers)).json()["total_attendees"] == 1
    assert (await client.get(f"{_PUBLIC}/{token}")).status_code == 404  # their link no longer works
    assert (await client.get(f"/api/v1/public/workshop-certificates/verify/{number}")).json()["valid"] is False
    assert (await client.delete(f"{_BASE}/{exam['id']}/attendees/{asha['id']}", headers=auth_headers)).status_code == 404
    # Their address can be added again as a fresh attendee.
    again = await client.post(f"{_BASE}/{exam['id']}/attendees", json={"attendees": [{"name": "Asha Rao", "email": "asha@example.com"}]}, headers=auth_headers)
    assert again.json()["added"] == 1


async def test_only_staff_who_manage_workshops_can_change_attendees(client, auth_headers):
    exam = await _exam(client, auth_headers)
    asha = (await _attendees(client, auth_headers, exam))["asha@example.com"]
    base = f"{_BASE}/{exam['id']}/attendees/{asha['id']}"
    assert (await client.patch(base, json={"name": "X"})).status_code in (401, 403)
    assert (await client.post(f"{base}/reset-submission")).status_code in (401, 403)
    assert (await client.delete(base)).status_code in (401, 403)
