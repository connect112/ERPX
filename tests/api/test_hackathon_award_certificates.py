"""
Hackathon winner certificates: every member of the 1st / 2nd / 3rd place teams gets their own certificate from that
place's design, optionally the other participants get a participation one, and each award has the full exam-certificate
toolkit (design, ID format, review, test emails) because each award is a certificate exam that belongs to the hackathon.
"""

import io
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select, update

from modules.hackathons import routes as hackathon_routes
from modules.hackathons.models import TaskSubmission
from modules.workshop_exams.models import WorkshopExamAttendee
from packages.email.registry import TEMPLATES
from tests.api.test_hackathon_certificates import _hackathon

pytestmark = pytest.mark.api

_HACK = "/api/v1/hackathons"
_EXAMS = "/api/v1/workshop-exams"


@pytest.fixture
def queued(monkeypatch):
    from modules.workshop_exams import routes as exam_routes

    ids: list[uuid.UUID] = []
    monkeypatch.setattr(hackathon_routes, "enqueue_certificates", lambda attendee_ids: ids.extend(attendee_ids))
    monkeypatch.setattr(exam_routes, "enqueue_certificates", lambda attendee_ids: ids.extend(attendee_ids))
    return ids


async def _awards(client, auth_headers, hackathon):
    r = await client.post(f"{_HACK}/{hackathon['id']}/certificates/awards", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()


def _by_award(overview):
    return {a["award"]: a for a in overview["awards"]}


async def _issue(client, auth_headers, hackathon, **body):
    return await client.post(f"{_HACK}/{hackathon['id']}/certificates/issue", json=body, headers=auth_headers)


def _png() -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (1600, 1131), (250, 250, 250)).save(out, format="PNG")
    return out.getvalue()


async def test_the_winning_teams_and_four_award_certificates_are_set_up_on_first_use(client, auth_headers, db_session):
    hackathon = await _hackathon(client, auth_headers, db_session)
    overview = await _awards(client, auth_headers, hackathon)
    awards = _by_award(overview)
    assert list(awards) == ["first", "second", "third", "participation"]
    assert [a["label"] for a in overview["awards"]] == ["1st place", "2nd place", "3rd place", "Participation"]
    assert [(t["team_name"], t["rank"], t["score"], sorted(m["name"] for m in t["members"])) for t in awards["first"]["teams"]] == [("Red", 1, 90, ["Asha Rao", "Ravi Kumar"])]
    assert [(t["team_name"], t["rank"], [m["name"] for m in t["members"]]) for t in awards["second"]["teams"]] == [("Blue", 2, ["Meena S"])]
    assert awards["third"]["teams"] == [] and awards["participation"]["teams"] == []
    assert all(a["has_design"] is False and a["review_required"] is False and a["sent"] == 0 for a in overview["awards"])
    # Kiran is on no team and no winning team: the only person a participation certificate could go to.
    assert overview["participation_in_teams"] == 0 and overview["participation_everyone"] == 1
    # Opening again changes nothing (the same four exams) and the award exams stay out of the Workshop Exams list.
    again = _by_award(await _awards(client, auth_headers, hackathon))
    assert {k: v["exam_id"] for k, v in again.items()} == {k: v["exam_id"] for k, v in awards.items()}
    assert (await client.get(_EXAMS, headers=auth_headers)).json() == []


async def test_a_tie_shares_the_place_and_the_next_place_is_skipped(client, auth_headers, db_session):
    hackathon = await _hackathon(client, auth_headers, db_session)
    await db_session.execute(update(TaskSubmission).values(score=90))  # Blue draws level with Red
    await db_session.flush()
    awards = _by_award(await _awards(client, auth_headers, hackathon))
    assert sorted(t["team_name"] for t in awards["first"]["teams"]) == ["Blue", "Red"]
    assert awards["second"]["teams"] == [] and awards["third"]["teams"] == []


async def test_the_preview_lists_every_member_of_a_winning_team_and_sends_nothing(client, auth_headers, db_session, queued):
    hackathon = await _hackathon(client, auth_headers, db_session)
    preview = await _issue(client, auth_headers, hackathon)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    plans = {p["award"]: p for p in body["awards"]}
    assert list(plans) == ["first", "second", "third"] and body["done"] is False and queued == []
    assert sorted(r["name"] for r in plans["first"]["recipients"]) == ["Asha Rao", "Ravi Kumar"]  # one each, a team of two gets two
    assert [r["name"] for r in plans["second"]["recipients"]] == ["Meena S"]  # a team of one gets one
    assert plans["third"]["recipients"] == [] and plans["first"]["will_send"] == 2 and plans["second"]["will_send"] == 1
    assert {r["status"] for p in plans.values() for r in p["recipients"]} == {"new"}

    everyone = (await _issue(client, auth_headers, hackathon, include_participation=True, participation_audience="all")).json()
    assert [r["name"] for r in {p["award"]: p for p in everyone["awards"]}["participation"]["recipients"]] == ["Kiran P"]
    in_teams = (await _issue(client, auth_headers, hackathon, include_participation=True, participation_audience="teams")).json()
    assert {p["award"]: p for p in in_teams["awards"]}["participation"]["recipients"] == []
    assert (await _issue(client, auth_headers, hackathon, include_participation=True, participation_audience="nobody")).status_code == 422


async def test_confirming_gives_each_winner_a_certificate_of_their_awards_exam_and_queues_the_emails(client, auth_headers, db_session, queued):
    hackathon = await _hackathon(client, auth_headers, db_session)
    overview = _by_award(await _awards(client, auth_headers, hackathon))
    done = await _issue(client, auth_headers, hackathon, include_participation=True, participation_audience="all", confirm=True)
    assert done.status_code == 200, done.text
    assert done.json()["done"] is True and done.json()["held_for_review"] == [] and "Queued 4 certificate email(s)" in done.json()["message"]
    assert len(queued) == 4

    def exam_attendees(award):
        return select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(overview[award]["exam_id"]))

    first = (await db_session.execute(exam_attendees("first"))).scalars().all()
    assert sorted(a.name for a in first) == ["Asha Rao", "Ravi Kumar"]
    assert all(a.certificate_only and a.certificate_number and a.info == {"team": "Red"} for a in first)
    assert [a.name for a in (await db_session.execute(exam_attendees("second"))).scalars()] == ["Meena S"]
    assert [a.name for a in (await db_session.execute(exam_attendees("participation"))).scalars()] == ["Kiran P"]
    assert (await db_session.execute(exam_attendees("third"))).scalars().all() == []
    expected = []
    for award in ("first", "second", "participation"):
        expected.extend(a.id for a in (await db_session.execute(exam_attendees(award))).scalars())
    assert sorted(queued) == sorted(expected)
    # Nobody is invited to anything or scored: the award exams are only for certificates.
    assert all(a.invited_at is None and a.submitted_at is None for a in first)


async def test_an_award_with_review_switched_on_is_held_for_review_and_can_be_reviewed_like_an_exam(client, auth_headers, db_session, queued):
    hackathon = await _hackathon(client, auth_headers, db_session)
    overview = _by_award(await _awards(client, auth_headers, hackathon))
    first_exam = overview["first"]["exam_id"]
    assert (await client.patch(f"{_EXAMS}/{first_exam}", json={"certificate_review": True}, headers=auth_headers)).status_code == 200
    done = (await _issue(client, auth_headers, hackathon, confirm=True)).json()
    assert done["held_for_review"] == ["1st place"] and len(queued) == 1  # only 2nd place (Meena) went out
    assert "Added for review" in done["message"]
    review = (await client.post(f"{_EXAMS}/{first_exam}/certificates/review", headers=auth_headers)).json()
    assert review["required"] is True and sorted(i["name"] for i in review["items"]) == ["Asha Rao", "Ravi Kumar"]
    assert all(i["certificate_number"] and i["certificate_verified_at"] is None for i in review["items"])
    # Not verified: sending the 1st place certificates is refused until they are (or everyone is verified).
    assert (await client.post(f"{_EXAMS}/{first_exam}/certificates/send-now", headers=auth_headers)).status_code == 409
    assert (await client.post(f"{_EXAMS}/{first_exam}/certificates/verify-all", headers=auth_headers)).status_code == 200
    assert (await client.post(f"{_EXAMS}/{first_exam}/certificates/send-now", headers=auth_headers)).status_code == 200
    assert len(queued) == 3


async def test_each_award_has_its_own_design_with_preview_and_a_winner_flavoured_test_email(client, auth_headers, db_session, monkeypatch):
    hackathon = await _hackathon(client, auth_headers, db_session)
    overview = _by_award(await _awards(client, auth_headers, hackathon))
    first_exam, second_exam = overview["first"]["exam_id"], overview["second"]["exam_id"]
    upload = await client.put(f"{_EXAMS}/{first_exam}/certificate/template", files={"file": ("gold.png", _png(), "image/png")}, headers=auth_headers)
    assert upload.status_code == 200, upload.text
    assert _by_award(await _awards(client, auth_headers, hackathon))["first"]["has_design"] is True
    assert _by_award(await _awards(client, auth_headers, hackathon))["second"]["has_design"] is False  # each place has its own

    preview = await client.post(f"{_EXAMS}/{first_exam}/certificate/preview", json={}, headers=auth_headers)
    assert preview.status_code == 200 and preview.content.startswith(b"%PDF")

    from modules.workshop_exams import routes as exam_routes

    sent = []

    async def fake_send(to, subject, text, html=None, attachments=None):
        sent.append((to, subject, text, attachments))
        return True

    monkeypatch.setattr(exam_routes.email_service, "send", fake_send)
    tested = await client.post(f"{_EXAMS}/{first_exam}/certificate/test-email", json={"email": "me@example.com"}, headers=auth_headers)
    assert tested.status_code == 200, tested.text
    to, subject, text, attachments = sent[0]
    assert to == "me@example.com" and subject.startswith("[TEST] Congratulations!") and "1st place" in subject and "DevSecStorm" in subject
    assert "Team Sample" in text and attachments[0].content.startswith(b"%PDF")
    # The participation certificate has its own wording.
    participation_exam = overview["participation"]["exam_id"]
    await client.put(f"{_EXAMS}/{participation_exam}/certificate/template", files={"file": ("p.png", _png(), "image/png")}, headers=auth_headers)
    participation = await client.post(f"{_EXAMS}/{participation_exam}/certificate/test-email", json={"email": "me@example.com"}, headers=auth_headers)
    assert participation.status_code == 200 and sent[1][1].startswith("[TEST] Your participation certificate") and second_exam != first_exam


async def test_the_real_certificate_email_names_the_place_the_team_and_the_hackathon_and_carries_that_places_pdf(client, auth_headers, db_session, queued, monkeypatch):
    from modules.workshop_exams import tasks

    hackathon = await _hackathon(client, auth_headers, db_session)
    await _awards(client, auth_headers, hackathon)
    await _issue(client, auth_headers, hackathon, confirm=True)
    asha = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "asha@example.com"))).scalar_one()
    meena = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "meena@example.com"))).scalar_one()

    mails = []

    async def fake_send(to, subject, text, html=None, attachments=None):
        mails.append((to, subject, text, attachments or []))
        return True

    @asynccontextmanager
    async def same_session():
        yield db_session

    monkeypatch.setattr(tasks.email_service, "send", fake_send)
    monkeypatch.setattr(tasks, "get_db_context", same_session)
    assert await tasks._send_certificate(asha.id) is True and await tasks._send_certificate(meena.id) is True
    (to1, subject1, text1, files1), (to2, subject2, _t, files2) = mails
    assert to1 == "asha@example.com" and subject1 == "Congratulations! Your certificate: 1st place in DevSecStorm" and "Red" in text1
    assert subject2 == "Congratulations! Your certificate: 2nd place in DevSecStorm" and to2 == "meena@example.com"
    assert files1[0].filename == "Certificate_Asha_Rao.pdf" and files1[0].content.startswith(b"%PDF") and files2[0].filename == "Certificate_Meena_S.pdf"


async def test_the_hackathon_certificate_emails_can_be_edited_in_the_mailing_section(client, auth_headers):
    keys = {t.key: t for t in TEMPLATES}
    winner, participation = keys["hackathon_winner_certificate"], keys["hackathon_participation_certificate"]
    assert winner.event_scoped and participation.event_scoped and winner.has_attachment and participation.has_attachment
    assert {v.name for v in winner.variables} >= {"full_name", "hackathon_title", "place", "team_name"}
    listed = (await client.get("/api/v1/email-templates", headers=auth_headers)).json()
    assert {"hackathon_winner_certificate", "hackathon_participation_certificate"} <= {t["key"] for t in (listed if isinstance(listed, list) else listed["items"])}


async def test_only_staff_who_manage_both_hackathons_and_workshops_can_use_it(client, auth_headers, db_session, staff_headers):
    hackathon = await _hackathon(client, auth_headers, db_session)
    for path in ("awards", "issue"):
        url = f"{_HACK}/{hackathon['id']}/certificates/{path}"
        assert (await client.post(url, json={}, headers=staff_headers)).status_code == 403
        assert (await client.post(url, json={})).status_code in (401, 403)
