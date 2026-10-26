"""
Students added by hand to a workshop exam: they are marked as manual, can be reviewed before anything is sent, get a
certificate without sitting the exam only when the admin explicitly forces it, and show "Manual - Not attended exam"
instead of a score in the results export.
"""

import csv
import io
import uuid

import pytest
from sqlalchemy import select

from modules.workshop_exams.models import WorkshopExamAttendee

pytestmark = pytest.mark.api

_BASE = "/api/v1/workshop-exams"
_PUBLIC = "/api/v1/public/workshop-exams"
_QUESTIONS = [{"text": "2 + 2?", "options": ["3", "4"], "correct_indices": [1], "marks": 1}]


@pytest.fixture
def queued(monkeypatch):
    from modules.workshop_exams import routes

    ids: list[uuid.UUID] = []
    monkeypatch.setattr(routes, "enqueue_certificates", lambda attendee_ids: ids.extend(attendee_ids))
    return ids


async def _exam(client, auth_headers, info_fields=None, review=False):
    body = {"title": "Workshop MCQ", "duration_minutes": 30}
    if info_fields:
        body["info_fields"] = info_fields
    created = await client.post(_BASE, json=body, headers=auth_headers)
    assert created.status_code == 201, created.text
    exam = created.json()
    await client.post(f"{_BASE}/{exam['id']}/questions", json={"questions": _QUESTIONS}, headers=auth_headers)
    await client.post(
        f"{_BASE}/{exam['id']}/attendees",
        json={"attendees": [{"name": "Asha Rao", "email": "asha@example.com"}]},
        headers=auth_headers,
    )
    assert (await client.post(f"{_BASE}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)).status_code == 200
    if review:
        await client.patch(f"{_BASE}/{exam['id']}", json={"certificate_review": True}, headers=auth_headers)
    return exam


async def _add(client, auth_headers, exam, **payload):
    body = {"name": "Meera Iyer", "email": "meera@example.com", **payload}
    return await client.post(f"{_BASE}/{exam['id']}/attendees/manual", json=body, headers=auth_headers)


async def _row(db_session, attendee_id):
    return (
        await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.id == uuid.UUID(attendee_id)))
    ).scalar_one()


async def _results(client, auth_headers, exam):
    csv_text = (await client.get(f"{_BASE}/{exam['id']}/results.csv", headers=auth_headers)).text
    return {r["Email"]: r for r in csv.DictReader(io.StringIO(csv_text))}


async def test_a_student_can_be_added_by_hand_and_is_marked_manual(client, auth_headers, db_session):
    exam = await _exam(client, auth_headers)
    added = await _add(client, auth_headers, exam, name="  Meera   Iyer ", email="Meera@Example.com")
    assert added.status_code == 201, added.text
    body = added.json()
    assert body["name"] == "Meera Iyer"
    assert body["email"] == "meera@example.com"
    assert body["added_manually"] is True
    assert body["certificate_forced"] is False
    # an ordinary exam attendee: gets a personal link, appears on the dashboard
    assert (await _row(db_session, body["id"])).access_token
    dashboard = (await client.get(f"{_BASE}/{exam['id']}/dashboard", headers=auth_headers)).json()
    assert dashboard["total_attendees"] == 2
    by_email = {a["email"]: a for a in dashboard["attendees"]}
    assert by_email["asha@example.com"]["added_manually"] is False


async def test_the_same_email_cannot_be_added_twice(client, auth_headers):
    exam = await _exam(client, auth_headers)
    assert (await _add(client, auth_headers, exam)).status_code == 201
    again = await _add(client, auth_headers, exam, email="MEERA@example.com")
    assert again.status_code == 409
    clash_with_registered = await _add(client, auth_headers, exam, email="asha@example.com")
    assert clash_with_registered.status_code == 409


async def test_extra_info_is_optional_but_checked(client, auth_headers):
    fields = [
        {"key": "college", "label": "College", "required": True, "type": "text"},
        {"key": "year", "label": "Year", "required": True, "type": "select", "options": ["1st", "2nd"]},
    ]
    exam = await _exam(client, auth_headers, info_fields=fields)
    ok = await _add(client, auth_headers, exam, info={"college": "NIT"})  # the year is not known: fine
    assert ok.status_code == 201, ok.text
    assert ok.json()["info"] == {"college": "NIT"}
    bad = await _add(client, auth_headers, exam, email="x@example.com", info={"year": "5th"})
    assert bad.status_code == 422


async def test_only_staff_who_manage_workshops_can_add_students(client, auth_headers):
    exam = await _exam(client, auth_headers)
    anonymous = await client.post(
        f"{_BASE}/{exam['id']}/attendees/manual", json={"name": "A", "email": "a@example.com"}
    )
    assert anonymous.status_code in (401, 403)


async def test_a_manual_student_who_did_not_attend_shows_manual_not_attended_instead_of_a_score(
    client, auth_headers, db_session
):
    exam = await _exam(client, auth_headers)
    await _add(client, auth_headers, exam)
    # Asha sits the exam; Meera never does
    asha = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "asha@example.com"))).scalars().first()
    start = (await client.post(f"{_PUBLIC}/{asha.access_token}/start")).json()
    await client.post(f"{_PUBLIC}/{asha.access_token}/submit", json={"answers": {start["questions"][0]["id"]: [1]}})

    rows = await _results(client, auth_headers, exam)
    assert rows["asha@example.com"]["Score"] == "1"
    assert rows["meera@example.com"]["Score"] == "Manual - Not attended exam"
    assert rows["meera@example.com"]["Total"] == ""


async def test_a_manual_student_who_did_attend_keeps_their_real_score(client, auth_headers, db_session):
    exam = await _exam(client, auth_headers)
    added = (await _add(client, auth_headers, exam)).json()
    token = (await _row(db_session, added["id"])).access_token
    start = (await client.post(f"{_PUBLIC}/{token}/start")).json()
    await client.post(f"{_PUBLIC}/{token}/submit", json={"answers": {start["questions"][0]["id"]: [1]}})
    rows = await _results(client, auth_headers, exam)
    assert rows["meera@example.com"]["Score"] == "1"
    assert rows["meera@example.com"]["Total"] == "1"


async def test_a_manual_student_without_the_exam_only_gets_a_certificate_when_forced(client, auth_headers, queued):
    exam = await _exam(client, auth_headers)
    meera = (await _add(client, auth_headers, exam)).json()
    url = f"{_BASE}/{exam['id']}/attendees/{meera['id']}/certificate/send"

    refused = await client.post(url, headers=auth_headers)  # no force
    assert refused.status_code == 422
    assert "hasn't taken the exam" in refused.text
    assert queued == []

    sent = await client.post(url, json={"force": True}, headers=auth_headers)
    assert sent.status_code == 200, sent.text
    assert queued == [uuid.UUID(meera["id"])]

    after = {a["email"]: a for a in (await client.get(f"{_BASE}/{exam['id']}/attendees", headers=auth_headers)).json()}
    assert after["meera@example.com"]["certificate_forced"] is True
    assert after["meera@example.com"]["certificate_number"]


async def test_force_is_only_for_manually_added_students(client, auth_headers, queued):
    exam = await _exam(client, auth_headers)
    asha = {a["email"]: a for a in (await client.get(f"{_BASE}/{exam['id']}/attendees", headers=auth_headers)).json()}[
        "asha@example.com"
    ]
    url = f"{_BASE}/{exam['id']}/attendees/{asha['id']}/certificate/send"
    refused = await client.post(url, json={"force": True}, headers=auth_headers)
    assert refused.status_code == 422
    assert queued == []


async def test_adding_with_a_certificate_includes_them_in_the_review_and_in_send_all(client, auth_headers, queued):
    exam = await _exam(client, auth_headers)
    meera = (await _add(client, auth_headers, exam, issue_certificate=True)).json()
    assert meera["certificate_forced"] is True

    review = (await client.post(f"{_BASE}/{exam['id']}/certificates/review", headers=auth_headers)).json()
    assert [i["email"] for i in review["items"]] == ["meera@example.com"]  # Asha has not sat the exam
    assert review["items"][0]["certificate_forced"] is True and review["items"][0]["added_manually"] is True

    sent = await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)
    assert sent.status_code == 200, sent.text
    assert queued == [uuid.UUID(meera["id"])]


async def test_a_forced_student_is_not_sent_an_exam_invite_link(client, auth_headers, monkeypatch):
    from modules.workshop_exams import routes

    invited: list = []
    monkeypatch.setattr(routes, "enqueue_invites", lambda ids: invited.extend(ids))
    exam = await _exam(client, auth_headers)
    await _add(client, auth_headers, exam, issue_certificate=True)
    await _add(client, auth_headers, exam, name="Kiran", email="kiran@example.com")
    result = await client.post(f"{_BASE}/{exam['id']}/invites", json={"resend_all": False}, headers=auth_headers)
    assert result.json()["queued"] == 2  # Asha and Kiran, not the forced Meera
    assert len(invited) == 2


async def test_a_manual_student_can_be_reviewed_and_previewed_before_anything_is_sent(client, auth_headers, db_session):
    exam = await _exam(client, auth_headers)
    meera = (await _add(client, auth_headers, exam)).json()
    base = f"{_BASE}/{exam['id']}/attendees/{meera['id']}/certificate"

    preview = await client.get(f"{base}/preview", headers=auth_headers)
    assert preview.status_code == 200, preview.text
    assert preview.headers["content-type"] == "application/pdf"

    fixed = await client.put(f"{base}/adjust", json={"size": 0.8, "dx": 0.01, "dy": 0.0}, headers=auth_headers)
    assert fixed.status_code == 200
    verified = await client.post(f"{base}/verify", json={"verified": True}, headers=auth_headers)
    assert verified.status_code == 200
    assert verified.json()["certificate_verified_at"]
    # reviewing alone gives no certificate
    row = await _row(db_session, meera["id"])
    assert row.certificate_forced is False and row.certificate_sent_at is None


async def test_a_registered_student_who_did_not_sit_the_exam_cannot_be_reviewed(client, auth_headers):
    exam = await _exam(client, auth_headers)
    asha = {a["email"]: a for a in (await client.get(f"{_BASE}/{exam['id']}/attendees", headers=auth_headers)).json()}[
        "asha@example.com"
    ]
    preview = await client.get(f"{_BASE}/{exam['id']}/attendees/{asha['id']}/certificate/preview", headers=auth_headers)
    assert preview.status_code == 422


async def test_review_required_waits_for_a_forced_student_to_be_verified(client, auth_headers, queued):
    exam = await _exam(client, auth_headers, review=True)
    await _add(client, auth_headers, exam, issue_certificate=True)
    blocked = await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)
    assert blocked.status_code == 409
    assert "reviewed" in blocked.text
    assert queued == []
