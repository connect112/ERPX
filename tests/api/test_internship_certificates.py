"""
Internship participation and completion certificates.

What must hold: each student is eligible for one certificate only (never both), only students with LMS access can be chosen,
the preview changes nothing, confirming creates the certificates and queues the emails (or holds them for review), nobody
is sent twice, a student's choice is fixed once their certificate exists, and each kind has its own design and wording
through the same certificate toolkit exams use.
"""

import io
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from modules.internship_learning import certificate_routes
from modules.workshop_exams import routes as exam_routes
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee
from tests.api.test_internship_learning import _world

pytestmark = pytest.mark.api

_INTERN = "/api/v1/our-internships"
_EXAMS = "/api/v1/workshop-exams"


@pytest.fixture
def queued(monkeypatch):
    ids: list[uuid.UUID] = []
    monkeypatch.setattr(certificate_routes, "enqueue_certificates", lambda attendee_ids: ids.extend(attendee_ids))
    monkeypatch.setattr(exam_routes, "enqueue_certificates", lambda attendee_ids: ids.extend(attendee_ids))
    return ids


def _url(internship, tail=""):
    return f"{_INTERN}/{internship['id']}/certificates{tail}"


def _png() -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (1600, 1131), (250, 250, 250)).save(out, format="PNG")
    return out.getvalue()


async def _open(client, headers, internship):
    r = await client.post(_url(internship, "/open"), headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _choose(client, headers, internship, selections, kind):
    return await client.put(_url(internship, "/eligibility"), json={"selection_ids": selections, "kind": kind}, headers=headers)


def _rows(overview):
    return {r["student_email"]: r for r in overview["rows"]}


def _info(overview):
    return {c["kind"]: c for c in overview["certificates"]}


async def _issue(client, headers, internship, **body):
    return await client.post(_url(internship, "/issue"), json=body, headers=headers)


async def _ready(client, headers, db_session, organization):
    """An internship with Asha chosen for completion and Meera for participation."""
    internship, people = await _world(client, headers, db_session, organization)
    await _open(client, headers, internship)
    asha, meera = people["asha@example.com"][0], people["meera@example.com"][0]
    assert (await _choose(client, headers, internship, [asha], "completion")).status_code == 200
    assert (await _choose(client, headers, internship, [meera], "participation")).status_code == 200
    return internship, people, asha, meera


# ------------------------------------------------------------ set-up


async def test_the_two_certificates_are_created_on_first_use_and_only_once(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    first = await _open(client, auth_headers, internship)
    assert set(_info(first)) == {"participation", "completion"}
    assert all(c["has_design"] is False and c["eligible_count"] == 0 and c["sent_count"] == 0 for c in first["certificates"])
    second = await _open(client, auth_headers, internship)
    assert {c["exam_id"] for c in second["certificates"]} == {c["exam_id"] for c in first["certificates"]}
    exams = (await db_session.execute(select(WorkshopExam).where(WorkshopExam.internship_id == uuid.UUID(internship["id"])))).scalars().all()
    assert {e.award for e in exams} == {"participation", "completion"} and len(exams) == 2
    assert {e.certificate_heading for e in exams} == {"Certificate of Participation", "Certificate of Completion"}


async def test_the_certificates_stay_out_of_the_exam_lists(client, auth_headers, db_session, organization):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    await _open(client, auth_headers, internship)
    assert (await client.get(_EXAMS, headers=auth_headers)).json() == []
    assert (await client.get(f"{_INTERN}/{internship['id']}/exams", headers=auth_headers)).json() == []
    assert (await client.get(f"{_INTERN}/{internship['id']}/exams/available", headers=auth_headers)).json() == []


# ------------------------------------------------------------ eligibility


async def test_each_student_is_on_one_list_and_can_be_moved_or_removed(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    await _open(client, auth_headers, internship)
    asha, meera = people["asha@example.com"][0], people["meera@example.com"][0]
    both = await _choose(client, auth_headers, internship, [asha, meera], "participation")
    assert both.status_code == 200 and {r["kind"] for r in both.json()["rows"]} == {"participation"}
    assert _info(both.json())["participation"]["eligible_count"] == 2
    moved = await _choose(client, auth_headers, internship, [asha], "completion")
    rows = _rows(moved.json())
    assert rows["asha@example.com"]["kind"] == "completion" and rows["meera@example.com"]["kind"] == "participation"
    info = _info(moved.json())
    assert (info["participation"]["eligible_count"], info["completion"]["eligible_count"]) == (1, 1)  # moved, never on both
    cleared = await _choose(client, auth_headers, internship, [asha], None)
    assert _rows(cleared.json())["asha@example.com"]["kind"] is None and _rows(cleared.json())["asha@example.com"]["delivery"] == "not_selected"
    assert (await client.get(_url(internship), headers=auth_headers)).json()["rows"][0]["student_name"]  # readable without manage


async def test_only_students_with_access_on_this_internship_can_be_chosen(client, auth_headers, db_session, organization):
    internship, people = await _world(client, auth_headers, db_session, organization)
    await _open(client, auth_headers, internship)
    ravi = people["ravi@example.com"][0]  # selected, no LMS access
    assert (await _choose(client, auth_headers, internship, [ravi], "completion")).status_code in (400, 422)
    assert (await _choose(client, auth_headers, internship, [str(uuid.uuid4())], "completion")).status_code in (400, 422)
    assert (await _choose(client, auth_headers, internship, [people["asha@example.com"][0]], "bogus")).status_code in (400, 422)
    assert (await client.put(_url(internship, "/eligibility"), json={"selection_ids": [], "kind": "completion"}, headers=auth_headers)).status_code in (400, 422)


# ------------------------------------------------------------ preview and release


async def test_the_preview_lists_who_gets_what_and_changes_nothing(client, auth_headers, db_session, organization, queued):
    internship, people, asha, meera = await _ready(client, auth_headers, db_session, organization)
    preview = await _issue(client, auth_headers, internship)
    assert preview.status_code == 200, preview.text
    body = preview.json()
    plans = {p["kind"]: p for p in body["plans"]}
    assert [r["email"] for r in plans["completion"]["recipients"]] == ["asha@example.com"]
    assert [r["email"] for r in plans["participation"]["recipients"]] == ["meera@example.com"]
    assert plans["completion"]["will_send"] == 1 and plans["completion"]["recipients"][0]["status"] == "new" and body["done"] is False
    assert queued == []
    assert (await db_session.execute(select(WorkshopExamAttendee))).scalars().all() == []


async def test_releasing_creates_the_certificates_queues_the_emails_and_never_sends_twice(client, auth_headers, db_session, organization, queued):
    internship, people, asha, meera = await _ready(client, auth_headers, db_session, organization)
    done = await _issue(client, auth_headers, internship, confirm=True)
    assert done.status_code == 200 and done.json()["done"] is True and "Queued 2" in done.json()["message"]
    attendees = (await db_session.execute(select(WorkshopExamAttendee))).scalars().all()
    assert {a.email for a in attendees} == {"asha@example.com", "meera@example.com"} and all(a.certificate_only and a.certificate_number for a in attendees)
    assert len({a.certificate_number for a in attendees}) == 2 and len(queued) == 2
    rows = _rows((await client.get(_url(internship), headers=auth_headers)).json())
    assert rows["asha@example.com"]["delivery"] == "queued" and rows["asha@example.com"]["certificate_number"]
    # until the email is delivered, releasing again sends the unsent ones once more, never makes a second certificate
    again = await _issue(client, auth_headers, internship, confirm=True)
    assert {p["kind"]: p["recipients"][0]["status"] for p in again.json()["plans"]} == {"completion": "resend", "participation": "resend"}
    assert len((await db_session.execute(select(WorkshopExamAttendee))).scalars().all()) == 2
    # once delivered, they are left alone
    for a in (await db_session.execute(select(WorkshopExamAttendee))).scalars():
        a.certificate_sent_at = datetime.now(timezone.utc)
    await db_session.flush()
    queued.clear()
    final = await _issue(client, auth_headers, internship, confirm=True)
    assert all(p["will_send"] == 0 and p["already_sent"] == 1 for p in final.json()["plans"]) and queued == []
    assert "Nobody" in final.json()["message"]
    tracked = (await client.get(_url(internship), headers=auth_headers)).json()
    assert {r["delivery"] for r in tracked["rows"] if r["kind"]} == {"sent"} and _info(tracked)["completion"]["sent_count"] == 1


async def test_one_kind_can_be_released_on_its_own(client, auth_headers, db_session, organization, queued):
    internship, people, asha, meera = await _ready(client, auth_headers, db_session, organization)
    done = await _issue(client, auth_headers, internship, kinds=["completion"], confirm=True)
    assert [p["kind"] for p in done.json()["plans"]] == ["completion"]
    attendees = (await db_session.execute(select(WorkshopExamAttendee))).scalars().all()
    assert [a.email for a in attendees] == ["asha@example.com"]
    assert (await _issue(client, auth_headers, internship, kinds=["bogus"])).status_code in (400, 422)


async def test_a_certificate_with_review_on_is_held_until_checked(client, auth_headers, db_session, organization, queued):
    internship, people, asha, meera = await _ready(client, auth_headers, db_session, organization)
    overview = await _open(client, auth_headers, internship)
    exam_id = _info(overview)["completion"]["exam_id"]
    assert (await client.put(f"{_EXAMS}/{exam_id}/certificate/template", files={"file": ("done.png", _png(), "image/png")}, headers=auth_headers)).status_code == 200
    assert (await client.patch(f"{_EXAMS}/{exam_id}", json={"certificate_review": True}, headers=auth_headers)).status_code == 200
    assert _info((await client.get(_url(internship), headers=auth_headers)).json())["completion"]["review_required"] is True
    done = await _issue(client, auth_headers, internship, confirm=True)
    assert done.json()["held_for_review"] == ["Completion"] and "Queued 1" in done.json()["message"]
    assert len(queued) == 1  # only Meera's participation certificate (no review) went out
    rows = _rows((await client.get(_url(internship), headers=auth_headers)).json())
    assert rows["asha@example.com"]["delivery"] == "held_for_review" and rows["meera@example.com"]["delivery"] == "queued"
    attendee = (await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.email == "asha@example.com"))).scalar_one()
    verified = await client.post(f"{_EXAMS}/{exam_id}/attendees/{attendee.id}/certificate/verify", json={"verified": True}, headers=auth_headers)
    assert verified.status_code == 200
    assert _rows((await client.get(_url(internship), headers=auth_headers)).json())["asha@example.com"]["delivery"] == "queued"


async def test_a_choice_is_fixed_once_the_certificate_exists(client, auth_headers, db_session, organization, queued):
    internship, people, asha, meera = await _ready(client, auth_headers, db_session, organization)
    await _issue(client, auth_headers, internship, kinds=["completion"], confirm=True)
    rows = _rows((await client.get(_url(internship), headers=auth_headers)).json())
    assert rows["asha@example.com"]["locked"] is True and rows["meera@example.com"]["locked"] is False
    moved = await _choose(client, auth_headers, internship, [asha], "participation")
    assert moved.status_code == 409 and "already has a certificate" in moved.text
    assert (await _choose(client, auth_headers, internship, [asha], None)).status_code == 409
    assert (await _choose(client, auth_headers, internship, [asha], "completion")).status_code == 200  # same choice is a no-op
    assert (await _choose(client, auth_headers, internship, [meera], "completion")).status_code == 200  # others are free
    # nobody ends up with both certificates
    attendees = (await db_session.execute(select(WorkshopExamAttendee.email))).scalars().all()
    assert len(attendees) == len(set(attendees))


# ------------------------------------------------------------ design and wording


async def test_each_kind_has_its_own_design_preview_and_email_wording(client, auth_headers, db_session, organization, monkeypatch):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    overview = _info(await _open(client, auth_headers, internship))
    completion, participation = overview["completion"]["exam_id"], overview["participation"]["exam_id"]
    upload = await client.put(f"{_EXAMS}/{completion}/certificate/template", files={"file": ("done.png", _png(), "image/png")}, headers=auth_headers)
    assert upload.status_code == 200, upload.text
    after = _info((await client.get(_url(internship), headers=auth_headers)).json())
    assert after["completion"]["has_design"] is True and after["participation"]["has_design"] is False  # each has its own
    preview = await client.post(f"{_EXAMS}/{completion}/certificate/preview", json={}, headers=auth_headers)
    assert preview.status_code == 200 and preview.content.startswith(b"%PDF")

    sent = []

    async def fake_send(to, subject, text, html=None, attachments=None):
        sent.append((to, subject, text, attachments))
        return True

    monkeypatch.setattr(exam_routes.email_service, "send", fake_send)
    assert (await client.post(f"{_EXAMS}/{completion}/certificate/test-email", json={"email": "me@example.com"}, headers=auth_headers)).status_code == 200
    await client.put(f"{_EXAMS}/{participation}/certificate/template", files={"file": ("p.png", _png(), "image/png")}, headers=auth_headers)
    assert (await client.post(f"{_EXAMS}/{participation}/certificate/test-email", json={"email": "me@example.com"}, headers=auth_headers)).status_code == 200
    assert sent[0][1].startswith("[TEST] Your internship completion certificate") and "Pentrix Cyber Internship" in sent[0][1]
    assert sent[1][1].startswith("[TEST] Your internship participation certificate") and sent[0][3][0].content.startswith(b"%PDF")


async def test_the_certificate_emails_are_editable_templates(client, auth_headers):
    listed = {t["key"]: t for t in (await client.get("/api/v1/email-templates", headers=auth_headers)).json()}
    assert {"internship_completion_certificate", "internship_participation_certificate"} <= set(listed)


# ------------------------------------------------------------ access


async def test_without_the_permission_nothing_can_be_chosen_or_released(client, auth_headers, staff_headers, db_session, organization):
    internship, people, asha, meera = await _ready(client, auth_headers, db_session, organization)
    assert (await client.get(_url(internship), headers=staff_headers)).status_code == 403
    assert (await client.post(_url(internship, "/open"), headers=staff_headers)).status_code == 403
    assert (await _choose(client, staff_headers, internship, [asha], None)).status_code == 403
    assert (await _issue(client, staff_headers, internship, confirm=True)).status_code == 403


async def test_one_organization_cannot_reach_anothers_certificates(client, auth_headers, db_session, organization):
    from modules.organizations.repository import OrganizationRepository
    from tests._fixtures import _make_user

    internship, people, asha, meera = await _ready(client, auth_headers, db_session, organization)
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other, is_superuser=True, email=f"x-{uuid.uuid4().hex[:6]}@other.example.com")
    outsider = {"Authorization": f"Bearer {token}"}
    assert (await client.get(_url(internship), headers=outsider)).status_code == 404
    assert (await client.post(_url(internship, "/open"), headers=outsider)).status_code == 404
    assert (await _choose(client, outsider, internship, [asha], "completion")).status_code == 404
    assert (await _issue(client, outsider, internship, confirm=True)).status_code == 404
