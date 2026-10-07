"""
Certificates for hackathon participants, sent from an exam: the preview, who is included for each audience,
that certificate-only people never get exam invites or skew the exam, resend of unsent ones, and the
interplay with the exam's own attendees.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from modules.hackathons.models import TaskSubmission
from modules.workshop_exams.models import WorkshopExamAttendee

pytestmark = pytest.mark.api

_EXAMS = "/api/v1/workshop-exams"
_HACK = "/api/v1/hackathons"
_PUBLIC = "/api/v1/public/workshop-exams"


def _dates():
    today = date.today()
    return {
        "registration_deadline": (today + timedelta(days=7)).isoformat(),
        "start_date": (today + timedelta(days=10)).isoformat(),
        "end_date": (today + timedelta(days=12)).isoformat(),
    }


@pytest.fixture
def queued(monkeypatch):
    """The attendee ids whose certificate email would be queued."""
    from modules.workshop_exams import routes

    ids: list[uuid.UUID] = []
    monkeypatch.setattr(routes, "enqueue_certificates", lambda attendee_ids: ids.extend(attendee_ids))
    return ids


async def _exam(client, auth_headers, attendees=None):
    created = await client.post(_EXAMS, json={"title": "DevSecStorm Certificates", "duration_minutes": 30}, headers=auth_headers)
    assert created.status_code == 201, created.text
    exam = created.json()
    questions = [{"text": "2 + 2?", "options": ["3", "4"], "correct_indices": [1], "marks": 1}]
    await client.post(f"{_EXAMS}/{exam['id']}/questions", json={"questions": questions}, headers=auth_headers)
    if attendees:
        await client.post(f"{_EXAMS}/{exam['id']}/attendees", json={"attendees": attendees}, headers=auth_headers)
    opened = await client.post(f"{_EXAMS}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    assert opened.status_code == 200, opened.text
    return exam


async def _hackathon(client, auth_headers, db_session):
    """Four people invited: Asha and Ravi on team Red (90 points) and Meena on team Blue (60 points), Kiran on no team."""
    created = await client.post(_HACK, json={"code": f"H-{uuid.uuid4().hex[:8]}", "title": "DevSecStorm", **_dates()}, headers=auth_headers)
    assert created.status_code == 201, created.text
    hackathon = created.json()
    people = [("Asha Rao", "asha@example.com"), ("Ravi Kumar", "ravi@example.com"), ("Meena S", "meena@example.com"), ("Kiran P", "kiran@example.com")]
    added = await client.post(
        f"{_HACK}/{hackathon['id']}/participants",
        json={"participants": [{"name": n, "email": e} for n, e in people]},
        headers=auth_headers,
    )
    assert added.status_code == 200, added.text
    for team, first in (("Red", people[0]), ("Blue", people[2])):
        made = await client.post(
            f"{_HACK}/{hackathon['id']}/teams",
            json={"name": team, "member": {"name": first[0], "email": first[1]}},
            headers=auth_headers,
        )
        assert made.status_code == 201, made.text
    roster = (await client.get(f"{_HACK}/{hackathon['id']}/roster", headers=auth_headers)).json()
    red = next(t for t in roster if t["name"] == "Red")
    blue = next(t for t in roster if t["name"] == "Blue")
    ravi = next(
        p for p in (await client.get(f"{_HACK}/{hackathon['id']}/participants", headers=auth_headers)).json() if p["email"] == "ravi@example.com"
    )
    added_member = await client.post(f"{_HACK}/{hackathon['id']}/teams/{red['id']}/members", json={"student_id": ravi["student_id"]}, headers=auth_headers)
    assert added_member.status_code == 201, added_member.text
    task = (await client.post(f"{_HACK}/{hackathon['id']}/problem-statements", json={"title": "One", "marks": 100}, headers=auth_headers)).json()
    for team, score in ((red, 90), (blue, 60)):
        db_session.add(
            TaskSubmission(
                team_id=uuid.UUID(team["id"]),
                problem_statement_id=uuid.UUID(task["id"]),
                repo_url="https://x.io/a",
                submitted_at=datetime.now(timezone.utc),
                score=score,
            )
        )
    await db_session.flush()
    return hackathon


async def _preview(client, auth_headers, exam, hackathon, audience="all", top_n=None, confirm=False):
    body = {"hackathon_id": hackathon["id"], "audience": audience, "confirm": confirm}
    if top_n:
        body["top_n"] = top_n
    return await client.post(f"{_EXAMS}/{exam['id']}/certificates/hackathon", json=body, headers=auth_headers)


def _names(response):
    return sorted(r["name"] for r in response.json()["recipients"])


async def test_the_preview_lists_who_would_get_a_certificate_for_each_audience_and_sends_nothing(client, auth_headers, db_session, queued):
    exam = await _exam(client, auth_headers)
    hackathon = await _hackathon(client, auth_headers, db_session)

    everyone = await _preview(client, auth_headers, exam, hackathon, "all")
    assert everyone.status_code == 200, everyone.text
    body = everyone.json()
    assert body["hackathon_title"] == "DevSecStorm" and body["will_send"] == 4 and body["sent"] is False
    assert _names(everyone) == ["Asha Rao", "Kiran P", "Meena S", "Ravi Kumar"] and {r["status"] for r in body["recipients"]} == {"new"}

    assert _names(await _preview(client, auth_headers, exam, hackathon, "teams")) == ["Asha Rao", "Meena S", "Ravi Kumar"]  # Kiran has no team
    assert _names(await _preview(client, auth_headers, exam, hackathon, "scored")) == ["Asha Rao", "Meena S", "Ravi Kumar"]
    assert _names(await _preview(client, auth_headers, exam, hackathon, "top", 1)) == ["Asha Rao", "Ravi Kumar"]  # team Red
    team = next(r for r in (await _preview(client, auth_headers, exam, hackathon, "top", 1)).json()["recipients"] if r["name"] == "Asha Rao")
    assert team["team_name"] == "Red"

    # A preview changes nothing: no attendees, nothing queued.
    attendees = (await client.get(f"{_EXAMS}/{exam['id']}/attendees", headers=auth_headers)).json()
    assert attendees == [] and queued == []
    # "top" needs a number, an unknown hackathon is a 404.
    assert (await _preview(client, auth_headers, exam, hackathon, "top")).status_code == 422
    assert (await client.post(f"{_EXAMS}/{exam['id']}/certificates/hackathon", json={"hackathon_id": str(uuid.uuid4())}, headers=auth_headers)).status_code == 404


async def test_confirming_adds_certificate_only_attendees_without_inviting_or_scoring_them(client, auth_headers, db_session, queued):
    exam = await _exam(client, auth_headers, attendees=[{"name": "Exam Taker", "email": "taker@example.com"}])
    hackathon = await _hackathon(client, auth_headers, db_session)

    sent = await _preview(client, auth_headers, exam, hackathon, "top", 1, confirm=True)
    assert sent.status_code == 200, sent.text
    assert sent.json()["sent"] is True and sent.json()["will_send"] == 2 and "2 certificate" in sent.json()["message"]

    rows = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalars().all()
    by_email = {r.email: r for r in rows}
    asha, ravi = by_email["asha@example.com"], by_email["ravi@example.com"]
    assert asha.certificate_only and ravi.certificate_only and not by_email["taker@example.com"].certificate_only
    assert asha.certificate_number and asha.certificate_number != ravi.certificate_number
    assert sorted(queued) == sorted([asha.id, ravi.id])

    # The exam's own numbers are about the exam: its one real attendee, nobody else.
    dash = (await client.get(f"{_EXAMS}/{exam['id']}/dashboard", headers=auth_headers)).json()
    assert dash["total_attendees"] == 1 and dash["not_started"] == 1 and dash["certificate_only"] == 2
    assert {a["email"]: a["certificate_only"] for a in dash["attendees"]}["asha@example.com"] is True
    # They are never invited to the exam, and aren't in its results export.
    invites = await client.post(f"{_EXAMS}/{exam['id']}/invites", json={}, headers=auth_headers)
    assert invites.json() == {"queued": 1}  # only the real attendee
    csv_text = (await client.get(f"{_EXAMS}/{exam['id']}/results.csv", headers=auth_headers)).text
    assert "taker@example.com" in csv_text and "asha@example.com" not in csv_text
    # Their certificate verifies, with an issue date.
    verify = (await client.get(f"/api/v1/public/workshop-certificates/verify/{asha.certificate_number}")).json()
    assert verify["valid"] is True and verify["attendee_name"] == "Asha Rao" and verify["issued_at"]


async def test_unsent_certificates_are_retried_and_sent_ones_and_exam_takers_are_left_alone(client, auth_headers, db_session, queued):
    exam = await _exam(client, auth_headers, attendees=[{"name": "Ravi Kumar", "email": "ravi@example.com"}])  # also sits the exam
    hackathon = await _hackathon(client, auth_headers, db_session)

    first = await _preview(client, auth_headers, exam, hackathon, "all", confirm=True)
    assert first.json()["will_send"] == 3  # Ravi takes the exam, so he gets his certificate through it
    assert {r["email"]: r["status"] for r in first.json()["recipients"]}["ravi@example.com"] == "on_exam"
    asha = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "asha@example.com"))).scalar_one()

    # Pressing it again before anything was delivered tries those again (no duplicates created).
    queued.clear()
    again = await _preview(client, auth_headers, exam, hackathon, "all", confirm=True)
    assert again.json()["will_send"] == 3 and {r["status"] for r in again.json()["recipients"] if r["email"] != "ravi@example.com"} == {"resend"}
    assert asha.id in queued and len(queued) == 3
    count = len((await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalars().all())
    assert count == 4  # Ravi plus the three added once

    # Once delivered they are left alone.
    for a in (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.certificate_only.is_(True)))).scalars():
        a.certificate_sent_at = datetime.now(timezone.utc)
    await db_session.flush()
    queued.clear()
    done = await _preview(client, auth_headers, exam, hackathon, "all", confirm=True)
    assert done.json()["will_send"] == 0 and done.json()["already_sent"] == 3 and queued == []
    assert done.json()["message"] == "Nobody needs a certificate right now."


async def test_the_certificate_email_carries_the_exams_design_and_the_persons_name(client, auth_headers, db_session, queued, monkeypatch):
    from modules.workshop_exams import tasks

    mails = []

    async def fake_send(to, subject, text, html=None, attachments=None):
        mails.append((to, subject, attachments or []))
        return True

    monkeypatch.setattr(tasks.email_service, "send", fake_send)

    @asynccontextmanager
    async def same_session():
        yield db_session

    monkeypatch.setattr(tasks, "get_db_context", same_session)

    exam = await _exam(client, auth_headers)
    await client.patch(f"{_EXAMS}/{exam['id']}", json={"certificate_heading": "Certificate of Achievement"}, headers=auth_headers)
    hackathon = await _hackathon(client, auth_headers, db_session)
    await _preview(client, auth_headers, exam, hackathon, "top", 1, confirm=True)
    asha = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "asha@example.com"))).scalar_one()

    assert await tasks._send_certificate(asha.id) is True
    to, subject, attachments = mails[0]
    assert to == "asha@example.com" and subject == "Your certificate: DevSecStorm Certificates"
    assert len(attachments) == 1 and attachments[0].content.startswith(b"%PDF") and attachments[0].filename == "Certificate_Asha_Rao.pdf"
    await db_session.refresh(asha)
    assert asha.certificate_sent_at is not None


async def test_someone_given_a_certificate_can_still_register_for_the_exam(client, auth_headers, db_session, queued):
    exam = await _exam(client, auth_headers)
    hackathon = await _hackathon(client, auth_headers, db_session)
    await _preview(client, auth_headers, exam, hackathon, "top", 1, confirm=True)

    code = (await client.get(f"{_EXAMS}/{exam['id']}", headers=auth_headers)).json()["public_code"]
    registered = await client.post(f"{_PUBLIC}/join/{code}/register", json={"name": "Asha R", "email": "asha@example.com", "info": {}})
    assert registered.status_code == 200, registered.text
    asha = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "asha@example.com"))).scalar_one()
    await db_session.refresh(asha)
    assert asha.certificate_only is False and asha.name == "Asha R"
    dash = (await client.get(f"{_EXAMS}/{exam['id']}/dashboard", headers=auth_headers)).json()
    assert dash["total_attendees"] == 1 and dash["certificate_only"] == 1  # Asha now sits the exam; Ravi only has a certificate
