"""
Optional review of certificates before they are sent: each person's certificate can be looked at, their name
printed smaller / moved, and marked verified; when review is required nothing is sent until all are verified;
a corrected email address never sends anything by itself.
"""

import io
import uuid

import pytest
from sqlalchemy import select

from modules.workshop_exams.certificate_template import (
    CertificateLayout,
    NameAdjust,
    build_templated_certificate_pdf,
    normalize_template,
)
from modules.workshop_exams.models import WorkshopExamAttendee
from tests.api.test_hackathon_certificates import _hackathon, _preview

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


@pytest.fixture
def readable_pdfs(monkeypatch):
    from reportlab import rl_config

    monkeypatch.setattr(rl_config, "pageCompression", 0)
    monkeypatch.setattr(rl_config, "useA85", 0)
    monkeypatch.setattr(rl_config, "invariant", 1)  # no timestamps, so equal certificates are equal bytes


def _design() -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (1600, 1131), (250, 250, 250)).save(out, format="PNG")
    return out.getvalue()


async def _exam(client, auth_headers, db_session, review=True, template=True):
    created = await client.post(_BASE, json={"title": "Workshop MCQ", "duration_minutes": 30}, headers=auth_headers)
    exam = created.json()
    await client.post(f"{_BASE}/{exam['id']}/questions", json={"questions": _QUESTIONS}, headers=auth_headers)
    people = [{"name": "Asha Rao", "email": "asha@example.com"}, {"name": "Ravi Kumar", "email": "ravi@example.com"}]
    await client.post(f"{_BASE}/{exam['id']}/attendees", json={"attendees": people}, headers=auth_headers)
    await client.post(f"{_BASE}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    if template:
        up = await client.put(
            f"{_BASE}/{exam['id']}/certificate/template",
            files={"file": ("d.png", _design(), "image/png")},
            headers=auth_headers,
        )
        assert up.status_code == 200, up.text
    if review:
        assert (await client.patch(f"{_BASE}/{exam['id']}", json={"certificate_review": True}, headers=auth_headers)).json()["certificate_review"]
    rows = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam["id"])))).scalars().all()
    for row in rows:
        start = (await client.post(f"{_PUBLIC}/{row.access_token}/start")).json()
        await client.post(f"{_PUBLIC}/{row.access_token}/submit", json={"answers": {start["questions"][0]["id"]: [1]}})
    return exam, {r.email: r for r in rows}


async def _review(client, auth_headers, exam):
    r = await client.post(f"{_BASE}/{exam['id']}/certificates/review", headers=auth_headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------- the name fix on the PDF ----------------


def test_a_names_size_and_position_can_be_adjusted_for_one_certificate(readable_pdfs):
    jpeg, w, h = normalize_template(_design())

    def build(adjust):
        return build_templated_certificate_pdf(
            template_jpeg=jpeg, width_px=w, height_px=h, layout=CertificateLayout(), attendee_name="Asha Rao",
            certificate_number="WS-1", verify_url="https://example.invalid", adjust=adjust,
        )

    plain, small, moved = build(None), build(NameAdjust(size=0.5)), build(NameAdjust(dx=0.1, dy=-0.05))
    assert plain == build(NameAdjust())  # no fix, same certificate
    assert small != plain and moved != plain and small != moved
    for bad in ({"size": 5}, {"size": 0}, {"dx": 1}, {"dy": -1}):
        with pytest.raises(ValueError):
            NameAdjust(**bad)


# ---------------- review and verification ----------------


async def test_review_lists_everyone_with_an_id_and_nobody_verified_at_first(client, db_session, auth_headers):
    exam, _ = await _exam(client, auth_headers, db_session)
    data = await _review(client, auth_headers, exam)
    assert data["required"] is True and [i["name"] for i in data["items"]] == ["Asha Rao", "Ravi Kumar"]
    assert all(i["certificate_number"] and i["certificate_verified_at"] is None and i["certificate_sent_at"] is None for i in data["items"])
    # Opening it again changes nothing (the same IDs).
    assert [i["certificate_number"] for i in (await _review(client, auth_headers, exam))["items"]] == [i["certificate_number"] for i in data["items"]]


async def test_sending_waits_until_every_certificate_is_verified_when_review_is_required(client, db_session, auth_headers, queued):
    exam, people = await _exam(client, auth_headers, db_session)
    url = f"{_BASE}/{exam['id']}/certificates/send-now"
    blocked = await client.post(url, headers=auth_headers)
    assert blocked.status_code == 409 and "2 certificate(s) haven't been reviewed" in blocked.text and queued == []

    asha = people["asha@example.com"]
    one = await client.post(f"{_BASE}/{exam['id']}/attendees/{asha.id}/certificate/verify", json={"verified": True}, headers=auth_headers)
    assert one.status_code == 200 and one.json()["certificate_verified_at"] is not None
    assert "1 certificate(s)" in (await client.post(url, headers=auth_headers)).text

    skipped = await client.post(f"{_BASE}/{exam['id']}/certificates/verify-all", headers=auth_headers)
    assert "Marked 1 " in skipped.json()["message"]
    sent = await client.post(url, headers=auth_headers)
    assert sent.status_code == 200 and sorted(queued) == sorted(a.id for a in people.values())


async def test_without_the_review_switch_sending_needs_no_verification(client, db_session, auth_headers, queued):
    exam, people = await _exam(client, auth_headers, db_session, review=False)
    assert (await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)).status_code == 200
    assert len(queued) == 2


async def test_changing_a_name_or_its_fix_means_the_certificate_needs_verifying_again(client, db_session, auth_headers):
    exam, people = await _exam(client, auth_headers, db_session)
    asha = people["asha@example.com"]
    base = f"{_BASE}/{exam['id']}/attendees/{asha.id}"
    await client.post(f"{base}/certificate/verify", json={"verified": True}, headers=auth_headers)

    renamed = await client.patch(base, json={"name": "Asha Rao-Iyer"}, headers=auth_headers)
    assert renamed.json()["certificate_verified_at"] is None
    await client.post(f"{base}/certificate/verify", json={"verified": True}, headers=auth_headers)
    same = await client.patch(base, json={"name": "Asha  Rao-Iyer"}, headers=auth_headers)  # spacing only: same name
    assert same.json()["certificate_verified_at"] is not None
    await client.patch(base, json={"email": "asha.new@example.com"}, headers=auth_headers)  # an email fix isn't a design fix
    assert (await _review(client, auth_headers, exam))["items"][0]["certificate_verified_at"] is not None

    fixed = await client.put(f"{base}/certificate/adjust", json={"size": 0.6, "dx": 0.02, "dy": 0}, headers=auth_headers)
    assert fixed.status_code == 200 and fixed.json()["certificate_adjust"] == {"size": 0.6, "dx": 0.02, "dy": 0.0}
    assert fixed.json()["certificate_verified_at"] is None
    reset = await client.put(f"{base}/certificate/adjust", json={"size": 1, "dx": 0, "dy": 0}, headers=auth_headers)
    assert reset.json()["certificate_adjust"] is None
    for bad in ({"size": 9}, {"dx": 2}):
        assert (await client.put(f"{base}/certificate/adjust", json=bad, headers=auth_headers)).status_code == 422


async def test_the_preview_is_the_certificate_that_will_be_emailed_with_the_fix_applied(client, db_session, auth_headers, readable_pdfs):
    exam, people = await _exam(client, auth_headers, db_session)
    asha = people["asha@example.com"]
    base = f"{_BASE}/{exam['id']}/attendees/{asha.id}"
    await _review(client, auth_headers, exam)
    before = await client.get(f"{base}/certificate/preview", headers=auth_headers)
    assert before.status_code == 200 and before.content.startswith(b"%PDF")
    await client.patch(base, json={"name": "A Very Long Name Indeed"}, headers=auth_headers)
    await client.put(f"{base}/certificate/adjust", json={"size": 0.5, "dx": 0, "dy": 0}, headers=auth_headers)
    after = await client.get(f"{base}/certificate/preview", headers=auth_headers)
    assert after.content != before.content

    # What gets emailed is the same document as the preview.
    from contextlib import asynccontextmanager

    from modules.workshop_exams import tasks

    mails = []

    async def fake_send(to, subject, text, html=None, attachments=None):
        mails.append((to, attachments))
        return True

    @asynccontextmanager
    async def same_session():
        yield db_session

    import pytest as _pytest

    mp = _pytest.MonkeyPatch()
    mp.setattr(tasks.email_service, "send", fake_send)
    mp.setattr(tasks, "get_db_context", same_session)
    try:
        assert await tasks._send_certificate(asha.id) is True
    finally:
        mp.undo()
    assert mails[0][1][0].content == after.content


async def test_people_with_no_certificate_cant_be_previewed_verified_or_sent(client, auth_headers, db_session):
    exam, people = await _exam(client, auth_headers, db_session)
    other = await client.post(f"{_BASE}/{exam['id']}/attendees", json={"attendees": [{"name": "Late Joiner", "email": "late@example.com"}]}, headers=auth_headers)
    assert other.status_code == 200
    late = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "late@example.com"))).scalar_one()
    base = f"{_BASE}/{exam['id']}/attendees/{late.id}/certificate"
    assert (await client.get(f"{base}/preview", headers=auth_headers)).status_code == 422
    assert (await client.post(f"{base}/verify", json={"verified": True}, headers=auth_headers)).status_code == 422
    assert (await client.post(f"{base}/send", headers=auth_headers)).status_code == 422
    assert "Late Joiner" not in [i["name"] for i in (await _review(client, auth_headers, exam))["items"]]


# ---------------- a corrected email address sends nothing by itself ----------------


async def test_correcting_an_email_sends_nothing_until_the_admin_chooses_to_send(client, db_session, auth_headers, queued, monkeypatch):
    from modules.workshop_exams import routes

    monkeypatch.setattr(routes, "enqueue_invite_best_effort", lambda attendee_id: queued.append(("link", attendee_id)))
    exam, people = await _exam(client, auth_headers, db_session, review=False)
    ravi = people["ravi@example.com"]
    base = f"{_BASE}/{exam['id']}/attendees/{ravi.id}"
    await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)
    queued.clear()
    from datetime import datetime, timezone

    await db_session.refresh(ravi)
    ravi.certificate_sent_at = datetime.now(timezone.utc)  # it went to the wrong address
    await db_session.flush()

    fixed = await client.patch(base, json={"email": "ravi.right@example.com"}, headers=auth_headers)
    assert fixed.status_code == 200 and queued == []  # nothing sent by changing the address
    sent = await client.post(f"{base}/certificate/send", headers=auth_headers)
    assert sent.status_code == 200 and "ravi.right@example.com" in sent.json()["message"]
    assert queued == [ravi.id]
    await db_session.refresh(ravi)
    assert ravi.certificate_sent_at is None and ravi.certificate_verified_at is not None  # the task sets it once delivered


# ---------------- hackathon participants and the ID format ----------------


async def test_hackathon_participants_wait_for_review_when_it_is_required(client, db_session, auth_headers, queued):
    from tests.api.test_hackathon_certificates import _exam as hackathon_exam

    exam = await hackathon_exam(client, auth_headers)
    await client.patch(f"{_BASE}/{exam['id']}", json={"certificate_review": True}, headers=auth_headers)
    hackathon = await _hackathon(client, auth_headers, db_session)
    done = await _preview(client, auth_headers, exam, hackathon, "all", confirm=True)
    assert done.status_code == 200, done.text
    assert done.json()["held_for_review"] is True and queued == [] and "Review certificates" in done.json()["message"]
    data = await _review(client, auth_headers, exam)
    assert sorted(i["name"] for i in data["items"]) == ["Asha Rao", "Kiran P", "Meena S", "Ravi Kumar"]
    assert all(i["certificate_only"] and i["certificate_number"] for i in data["items"])
    # Sending needs them verified first.
    assert (await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)).status_code == 409
    await client.post(f"{_BASE}/{exam['id']}/certificates/verify-all", headers=auth_headers)
    assert (await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)).status_code == 200
    assert len(queued) == 4


async def test_the_id_format_cant_change_once_certificates_have_ids(client, db_session, auth_headers):
    exam, _ = await _exam(client, auth_headers, db_session, review=False)
    url = f"{_BASE}/{exam['id']}"
    assert (await client.patch(url, json={"certificate_id_pattern": "GIR-{#4}"}, headers=auth_headers)).status_code == 200
    await _review(client, auth_headers, exam)  # gives everyone an ID
    locked = await client.patch(url, json={"certificate_id_pattern": "OTHER-{#4}"}, headers=auth_headers)
    assert locked.status_code == 422 and "already have an ID" in locked.text
    same = await client.patch(url, json={"certificate_id_pattern": "GIR-{#4}", "certificate_review": True}, headers=auth_headers)
    assert same.status_code == 200  # saving the same format alongside other settings is fine


async def test_only_staff_who_manage_workshops_can_review(client, auth_headers, db_session):
    exam, people = await _exam(client, auth_headers, db_session)
    asha = people["asha@example.com"]
    for method, path in (
        ("post", f"{_BASE}/{exam['id']}/certificates/review"),
        ("post", f"{_BASE}/{exam['id']}/certificates/verify-all"),
        ("get", f"{_BASE}/{exam['id']}/attendees/{asha.id}/certificate/preview"),
        ("post", f"{_BASE}/{exam['id']}/attendees/{asha.id}/certificate/send"),
        ("put", f"{_BASE}/{exam['id']}/attendees/{asha.id}/certificate/adjust"),
    ):
        assert (await getattr(client, method)(path)).status_code in (401, 403), path
