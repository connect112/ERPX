"""
Internship offer letters: the PDF template and where details go on it, the email, releasing the letters in bulk, and the
background send of each one (status per student, retries, and a clear reason when one fails).
"""

import io
import uuid

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from sqlalchemy import select

from modules.organizations.repository import OrganizationRepository
from modules.our_internships import offers as offers_module
from modules.our_internships import routes, tasks
from modules.our_internships.models import InternshipSelection, OfferStatus, OurInternship
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_INST = "/api/v1/institutions"
_EVENTS = "/api/v1/institution-events"
_INTERN = "/api/v1/our-internships"
_LIST = "Name,Email\nAsha Rao,asha@example.com\nMeera Iyer,meera@example.com\nRavi Kumar,ravi@example.com\n"

NAME_FIELD = {"key": "name", "page": 1, "x": 0.5, "y": 0.4, "align": "center", "font": "serif_bold", "font_size": 0.03}
REFERENCE_FIELD = {"key": "reference", "page": 1, "x": 0.1, "y": 0.9}
INSTITUTION_FIELD = {"key": "institution", "page": 1, "x": 0.1, "y": 0.5}


def pdf_bytes(pages=1) -> bytes:
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=(595, 842))
    for i in range(pages):
        c.drawString(72, 770, f"PENTRIX OFFER OF INTERNSHIP page {i + 1}")
        c.showPage()
    c.save()
    return out.getvalue()


def text_of(pdf: bytes, page=0) -> str:
    return " ".join(PdfReader(io.BytesIO(pdf)).pages[page].extract_text().split())


@pytest.fixture
def queued(monkeypatch):
    """Collects what would be queued, so nothing needs a message broker."""
    ids: list[uuid.UUID] = []
    monkeypatch.setattr(routes, "enqueue_offers", lambda selection_ids: ids.extend(selection_ids))
    return ids


async def _setup(client, headers, select_emails=("asha@example.com", "meera@example.com", "ravi@example.com")):
    inst = (await client.post(_INST, json={"name": "Sri Venkateswara College", "location": "Tirupati", "faculty_name": "Dr. L"}, headers=headers)).json()
    event = (
        await client.post(
            f"{_INST}/{inst['id']}/events",
            json={"name": "Workshop", "event_type": "workshop", "start_date": "2026-11-10", "end_date": "2026-11-11"},
            headers=headers,
        )
    ).json()
    await client.post(f"{_EVENTS}/{event['id']}/students/import", data={"text": _LIST}, headers=headers)
    internship = (
        await client.post(_INTERN, json={"title": "Pentrix Cyber Internship", "scope": "all"}, headers=headers)
    ).json()
    board = (await client.get(f"{_INTERN}/{internship['id']}/performance", headers=headers)).json()
    ids = {s["email"]: s["student_id"] for s in board["students"]}
    if select_emails:
        r = await client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": [ids[e] for e in select_emails]}, headers=headers)
        assert r.status_code == 200, r.text
    return internship, ids


async def _upload(client, headers, internship, data=None, name="letter.pdf"):
    return await client.put(
        f"{_INTERN}/{internship['id']}/offer/template", files={"file": (name, pdf_bytes() if data is None else data, "application/pdf")}, headers=headers
    )


async def _layout(client, headers, internship, *fields):
    return await client.put(f"{_INTERN}/{internship['id']}/offer/layout", json={"fields": list(fields or [NAME_FIELD])}, headers=headers)


async def _ready(client, headers, **kw):
    internship, ids = await _setup(client, headers, **kw)
    assert (await _upload(client, headers, internship)).status_code == 200
    assert (await _layout(client, headers, internship, NAME_FIELD, REFERENCE_FIELD, INSTITUTION_FIELD)).status_code == 200
    return internship, ids


async def _selections(db_session, internship) -> dict[str, InternshipSelection]:
    from modules.institutions.models import InstitutionStudent

    rows = (
        await db_session.execute(
            select(InternshipSelection, InstitutionStudent.email)
            .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
            .where(InternshipSelection.internship_id == uuid.UUID(internship["id"]))
        )
    ).all()
    return {email: sel for sel, email in rows}


def _same_session(monkeypatch, db_session):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx():
        yield db_session

    monkeypatch.setattr(tasks, "get_db_context", _ctx)


class _Mailbox:
    def __init__(self, ok=True):
        self.ok, self.sent = ok, []

    async def send(self, to, subject, text, html=None, attachments=None):
        self.sent.append({"to": to, "subject": subject, "text": text, "html": html, "attachments": attachments or []})
        return self.ok


# ------------------------------------------------------------- the template


async def test_a_new_internship_has_no_template_and_says_what_is_missing(client, auth_headers):
    internship, _ = await _setup(client, auth_headers, select_emails=())
    settings = (await client.get(f"{_INTERN}/{internship['id']}/offer", headers=auth_headers)).json()
    assert settings["has_template"] is False and settings["layout"] is None
    assert settings["email_is_default"] is True and "{{full_name}}" in settings["email_body"]
    assert settings["missing"] == ["Upload the offer letter as a PDF.", "Select at least one student."]
    assert set(settings["placeholders"]) == {"full_name", "internship_title", "institution", "reference"}
    assert settings["counts"]["selected"] == 0


async def test_a_pdf_template_is_uploaded_downloaded_and_removed(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    original = pdf_bytes(2)
    up = await _upload(client, auth_headers, internship, original, "My Offer Letter.pdf")
    assert up.status_code == 200, up.text
    assert (up.json()["template_filename"], up.json()["template_pages"]) == ("My Offer Letter.pdf", 2)
    assert up.json()["missing"] == ["Mark where the student's name goes on the letter."]
    down = await client.get(f"{_INTERN}/{internship['id']}/offer/template", headers=auth_headers)
    assert down.status_code == 200 and down.content == original
    assert down.headers["content-type"] == "application/pdf" and down.headers["x-content-type-options"] == "nosniff"
    # the bytes are never part of ordinary JSON
    assert "template_data" not in (await client.get(f"{_INTERN}/{internship['id']}", headers=auth_headers)).text
    gone = await client.delete(f"{_INTERN}/{internship['id']}/offer/template", headers=auth_headers)
    assert gone.json()["has_template"] is False
    assert (await client.get(f"{_INTERN}/{internship['id']}/offer/template", headers=auth_headers)).status_code == 404


async def test_a_file_that_is_not_a_usable_pdf_is_refused_with_the_reason(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    for data, name, reason in (
        (b"hello", "letter.pdf", "not a PDF"),
        (b"", "letter.pdf", "empty"),
        (b"%PDF-1.4 broken", "letter.pdf", "could not be read"),
        (pdf_bytes(11), "long.pdf", "at most 10 pages"),
    ):
        r = await _upload(client, auth_headers, internship, data, name)
        assert r.status_code == 422, (name, r.text)
        assert reason in r.json()["error"]["message"]


# --------------------------------------------------------------- the layout


async def test_where_details_go_on_the_letter_is_saved_and_checked(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    assert (await _layout(client, auth_headers, internship)).status_code == 422  # no template yet
    await _upload(client, auth_headers, internship, pdf_bytes(1))
    saved = await _layout(client, auth_headers, internship, NAME_FIELD, REFERENCE_FIELD)
    assert saved.status_code == 200
    assert [f["key"] for f in saved.json()["layout"]["fields"]] == ["name", "reference"]
    assert saved.json()["missing"] == []

    too_far = await _layout(client, auth_headers, internship, {**NAME_FIELD, "page": 2})
    assert too_far.status_code == 422 and "page 2 does not exist" in too_far.json()["error"]["message"]
    no_name = await _layout(client, auth_headers, internship, REFERENCE_FIELD)
    assert no_name.status_code == 422
    twice = await _layout(client, auth_headers, internship, NAME_FIELD, NAME_FIELD)
    assert twice.status_code == 422
    off_page = await _layout(client, auth_headers, internship, {**NAME_FIELD, "x": 1.5})
    assert off_page.status_code == 422
    # a rejected change leaves the saved layout alone
    assert [f["key"] for f in (await client.get(f"{_INTERN}/{internship['id']}/offer", headers=auth_headers)).json()["layout"]["fields"]] == ["name", "reference"]


async def test_a_shorter_replacement_template_drops_fields_on_pages_it_no_longer_has(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    await _upload(client, auth_headers, internship, pdf_bytes(2))
    await _layout(client, auth_headers, internship, NAME_FIELD, {"key": "date", "page": 2, "x": 0.2, "y": 0.2})
    replaced = await _upload(client, auth_headers, internship, pdf_bytes(1))
    assert [f["key"] for f in replaced.json()["layout"]["fields"]] == ["name"]


# ----------------------------------------------------------------- the email


async def test_the_email_wording_can_be_customised_and_reset(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    custom = await client.put(
        f"{_INTERN}/{internship['id']}/offer/email",
        json={"subject": "Welcome aboard, {{full_name}}", "body": "Dear {{full_name}}, your reference is {{reference}}.", "offer_date": "2026-11-20"},
        headers=auth_headers,
    )
    assert custom.status_code == 200
    body = custom.json()
    assert (body["email_subject"], body["email_is_default"], body["offer_date"]) == ("Welcome aboard, {{full_name}}", False, "2026-11-20")
    reset = await client.put(f"{_INTERN}/{internship['id']}/offer/email", json={"subject": "  ", "body": ""}, headers=auth_headers)
    assert reset.json()["email_is_default"] is True and "{{internship_title}}" in reset.json()["email_subject"]


async def test_a_mistyped_placeholder_is_caught_when_saving_not_when_sending(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    r = await client.put(f"{_INTERN}/{internship['id']}/offer/email", json={"subject": "Hi {{fullname}}", "body": "{{nope}}"}, headers=auth_headers)
    assert r.status_code == 422
    message = r.json()["error"]["message"]
    assert "{{fullname}}" in message and "{{nope}}" in message and "{{full_name}}" in message


# ------------------------------------------------------------------ previews


async def test_a_sample_letter_can_be_previewed_with_saved_or_unsaved_positions(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    assert (await client.post(f"{_INTERN}/{internship['id']}/offer/preview", json={}, headers=auth_headers)).status_code == 422
    await _upload(client, auth_headers, internship)
    await _layout(client, auth_headers, internship)
    saved = await client.post(f"{_INTERN}/{internship['id']}/offer/preview", json={}, headers=auth_headers)
    assert saved.status_code == 200 and saved.headers["content-type"] == "application/pdf"
    assert "Asha Rao" in text_of(saved.content) and "PENTRIX OFFER OF INTERNSHIP" in text_of(saved.content)
    # positions that are not saved yet can be tried out, and they are not saved by trying
    trial = await client.post(
        f"{_INTERN}/{internship['id']}/offer/preview",
        json={"layout": {"fields": [NAME_FIELD, {"key": "internship", "page": 1, "x": 0.1, "y": 0.6}]}},
        headers=auth_headers,
    )
    assert "Pentrix Cyber Internship" in text_of(trial.content)
    assert [f["key"] for f in (await client.get(f"{_INTERN}/{internship['id']}/offer", headers=auth_headers)).json()["layout"]["fields"]] == ["name"]


async def test_one_students_letter_can_be_checked_before_anything_is_sent(client, auth_headers):
    internship, ids = await _ready(client, auth_headers)
    r = await client.get(f"{_INTERN}/{internship['id']}/selected/{ids['meera@example.com']}/offer.pdf", headers=auth_headers)
    assert r.status_code == 200
    text = text_of(r.content)
    assert "Meera Iyer" in text and "Sri Venkateswara College" in text and "OFR-" in text
    assert "filename*=UTF-8''Internship_Offer_Meera_Iyer.pdf" in r.headers["content-disposition"]
    stranger = await client.get(f"{_INTERN}/{internship['id']}/selected/{uuid.uuid4()}/offer.pdf", headers=auth_headers)
    assert stranger.status_code == 404


async def test_a_test_email_with_a_sample_letter_goes_to_one_address(client, auth_headers, monkeypatch):
    internship, _ = await _ready(client, auth_headers)
    box = _Mailbox()
    monkeypatch.setattr(offers_module.email_service, "send", box.send)
    r = await client.post(f"{_INTERN}/{internship['id']}/offer/test-email", json={"to_email": "me@example.com"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    mail = box.sent[0]
    assert mail["to"] == "me@example.com" and mail["subject"].startswith("[Test] ")
    assert mail["attachments"][0].mime_type == "application/pdf" and "Asha Rao" in text_of(mail["attachments"][0].content)

    failing = _Mailbox(ok=False)
    monkeypatch.setattr(offers_module.email_service, "send", failing.send)
    bad = await client.post(f"{_INTERN}/{internship['id']}/offer/test-email", json={"to_email": "me@example.com"}, headers=auth_headers)
    assert bad.status_code == 503


# ------------------------------------------------------------------- release


async def test_offers_cannot_be_released_until_the_letter_is_ready_and_someone_is_selected(client, auth_headers, queued):
    internship, _ = await _setup(client, auth_headers, select_emails=())
    release = lambda: client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)  # noqa: E731
    assert (await release()).status_code == 422  # no template
    await _upload(client, auth_headers, internship)
    assert (await release()).status_code == 422  # no name placed
    await _layout(client, auth_headers, internship)
    assert (await release()).status_code == 422  # nobody selected
    assert queued == []


async def test_releasing_queues_a_letter_per_student_with_its_own_reference(client, auth_headers, db_session, queued):
    internship, _ = await _ready(client, auth_headers)
    r = await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert (r.json()["queued"], r.json()["already_sent"]) == (3, 0)
    rows = await _selections(db_session, internship)
    assert {s.offer_status for s in rows.values()} == {OfferStatus.QUEUED}
    references = sorted(s.offer_reference for s in rows.values())
    assert len(set(references)) == 3 and all(ref.startswith("OFR-") for ref in references)
    assert sorted(queued) == sorted(s.id for s in rows.values())

    after = (await client.get(f"{_INTERN}/{internship['id']}", headers=auth_headers)).json()
    assert after["status"] == "offers_released" and after["offers_released_at"]
    listed = (await client.get(f"{_INTERN}/{internship['id']}/selected", headers=auth_headers)).json()["items"]
    assert {i["offer_status"] for i in listed} == {"queued"} and all(i["offer_reference"] for i in listed)

    # pressing it again does not queue them twice
    queued.clear()
    again = await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    assert again.json()["queued"] == 0 and queued == []


async def test_only_the_chosen_students_are_released_and_they_must_be_on_the_selected_list(client, auth_headers, db_session, queued):
    internship, ids = await _ready(client, auth_headers, select_emails=("asha@example.com", "meera@example.com"))
    r = await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={"student_ids": [ids["asha@example.com"]]}, headers=auth_headers)
    assert r.json()["queued"] == 1
    rows = await _selections(db_session, internship)
    assert rows["asha@example.com"].offer_status == OfferStatus.QUEUED and rows["meera@example.com"].offer_status == OfferStatus.NOT_SENT
    not_selected = await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={"student_ids": [ids["ravi@example.com"]]}, headers=auth_headers)
    assert not_selected.status_code == 422


async def test_students_selected_later_get_the_next_references_and_keep_earlier_ones(client, auth_headers, db_session, queued):
    internship, ids = await _ready(client, auth_headers, select_emails=("asha@example.com", "meera@example.com"))
    await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    first = {e: s.offer_reference for e, s in (await _selections(db_session, internship)).items()}
    await client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": [ids["ravi@example.com"]]}, headers=auth_headers)
    queued.clear()
    more = await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    assert more.json()["queued"] == 1
    rows = await _selections(db_session, internship)
    assert rows["asha@example.com"].offer_reference == first["asha@example.com"]
    assert len({s.offer_reference for s in rows.values()}) == 3


async def test_if_the_queue_is_unreachable_nothing_is_marked_as_sending(client, auth_headers, db_session, monkeypatch):
    internship, _ = await _ready(client, auth_headers)

    def broker_down(_ids):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(routes, "enqueue_offers", broker_down)
    r = await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    assert r.status_code == 503
    rows = await _selections(db_session, internship)
    assert {s.offer_status for s in rows.values()} == {OfferStatus.NOT_SENT}
    # and releasing works once the queue is back
    monkeypatch.setattr(routes, "enqueue_offers", lambda ids: None)
    assert (await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)).json()["queued"] == 3


# ------------------------------------------------------------ the background send


async def test_a_queued_offer_is_emailed_with_the_stamped_letter_and_marked_sent(client, auth_headers, db_session, monkeypatch, queued):
    internship, _ = await _ready(client, auth_headers, select_emails=("asha@example.com",))
    await client.put(
        f"{_INTERN}/{internship['id']}/offer/email",
        json={"subject": "Offer for {{full_name}}", "body": "Dear {{full_name}}, ref {{reference}} at {{institution}} for {{internship_title}}."},
        headers=auth_headers,
    )
    await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    selection = (await _selections(db_session, internship))["asha@example.com"]
    box = _Mailbox()
    _same_session(monkeypatch, db_session)
    monkeypatch.setattr(tasks.email_service, "send", box.send)

    assert await tasks._send_offer(selection.id) is True
    mail = box.sent[0]
    assert mail["to"] == "asha@example.com" and mail["subject"] == "Offer for Asha Rao"
    assert f"ref {selection.offer_reference} at Sri Venkateswara College for Pentrix Cyber Internship." in mail["text"]
    attachment = mail["attachments"][0]
    assert attachment.filename == "Internship_Offer_Asha_Rao.pdf" and attachment.mime_type == "application/pdf"
    letter = text_of(attachment.content)
    assert "Asha Rao" in letter and selection.offer_reference in letter and "PENTRIX OFFER OF INTERNSHIP" in letter
    await db_session.refresh(selection)
    assert (selection.offer_status, selection.offer_attempts, selection.offer_error) == (OfferStatus.SENT, 1, None)
    assert selection.offer_sent_at is not None

    # running it again (a duplicate task) does not send a second email
    assert await tasks._send_offer(selection.id) is True
    assert len(box.sent) == 1


async def test_a_failed_send_is_retried_then_marked_failed_with_the_reason_and_can_be_sent_again(client, auth_headers, db_session, monkeypatch, queued):
    internship, _ = await _ready(client, auth_headers, select_emails=("asha@example.com",))
    await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    selection = (await _selections(db_session, internship))["asha@example.com"]
    box = _Mailbox(ok=False)
    _same_session(monkeypatch, db_session)
    monkeypatch.setattr(tasks.email_service, "send", box.send)

    for attempt in range(1, tasks.MAX_ATTEMPTS):
        assert await tasks._send_offer(selection.id) is False  # try again later
        await db_session.refresh(selection)
        assert (selection.offer_status, selection.offer_attempts) == (OfferStatus.QUEUED, attempt)
    assert await tasks._send_offer(selection.id) is True  # out of attempts: stop retrying
    await db_session.refresh(selection)
    assert selection.offer_status == OfferStatus.FAILED and "could not be delivered" in selection.offer_error
    listed = (await client.get(f"{_INTERN}/{internship['id']}/selected", headers=auth_headers)).json()["items"][0]
    assert (listed["offer_status"], "delivered" in listed["offer_error"]) == ("failed", True)

    # releasing again picks up the failed one, with its reference unchanged
    reference = selection.offer_reference
    again = await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    assert again.json()["queued"] == 1
    await db_session.refresh(selection)
    assert (selection.offer_status, selection.offer_attempts, selection.offer_error, selection.offer_reference) == (OfferStatus.QUEUED, 0, None, reference)


async def test_an_error_while_building_or_sending_is_recorded_not_lost(client, auth_headers, db_session, monkeypatch, queued):
    internship, _ = await _ready(client, auth_headers, select_emails=("asha@example.com",))
    await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    selection = (await _selections(db_session, internship))["asha@example.com"]
    _same_session(monkeypatch, db_session)

    async def boom(*a, **k):
        raise RuntimeError("SMTP exploded")

    monkeypatch.setattr(tasks.email_service, "send", boom)
    assert await tasks._send_offer(selection.id) is False
    await db_session.refresh(selection)
    assert "RuntimeError: SMTP exploded" in selection.offer_error and selection.offer_status == OfferStatus.QUEUED


async def test_the_send_does_nothing_for_an_offer_that_is_no_longer_wanted(client, auth_headers, db_session, monkeypatch, queued):
    internship, ids = await _ready(client, auth_headers, select_emails=("asha@example.com", "meera@example.com"))
    box = _Mailbox()
    _same_session(monkeypatch, db_session)
    monkeypatch.setattr(tasks.email_service, "send", box.send)
    rows = await _selections(db_session, internship)
    # never released: still "not sent", so a stray task must not send it
    assert await tasks._send_offer(rows["asha@example.com"].id) is True
    # removed from the list while queued
    await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    await client.delete(f"{_INTERN}/{internship['id']}/selected/{ids['meera@example.com']}", headers=auth_headers)
    assert await tasks._send_offer(rows["meera@example.com"].id) is True
    assert box.sent == []


async def test_a_sent_offer_is_left_alone_unless_a_resend_is_asked_for(client, auth_headers, db_session, monkeypatch, queued):
    internship, ids = await _ready(client, auth_headers, select_emails=("asha@example.com",))
    await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    selection = (await _selections(db_session, internship))["asha@example.com"]
    _same_session(monkeypatch, db_session)
    monkeypatch.setattr(tasks.email_service, "send", _Mailbox().send)
    await tasks._send_offer(selection.id)

    same = await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    assert (same.json()["queued"], same.json()["already_sent"]) == (0, 1)
    assert "already sent" in same.json()["message"]
    again = await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={"student_ids": [ids["asha@example.com"]], "resend": True}, headers=auth_headers)
    assert again.json()["queued"] == 1
    await db_session.refresh(selection)
    assert selection.offer_status == OfferStatus.QUEUED and selection.offer_sent_at is not None


async def test_a_template_cannot_be_removed_once_offers_have_gone_out(client, auth_headers, queued):
    internship, _ = await _ready(client, auth_headers)
    await client.post(f"{_INTERN}/{internship['id']}/offers/release", json={}, headers=auth_headers)
    r = await client.delete(f"{_INTERN}/{internship['id']}/offer/template", headers=auth_headers)
    assert r.status_code == 409 and "already been sent" in r.json()["error"]["message"]
    assert (await client.get(f"{_INTERN}/{internship['id']}/offer", headers=auth_headers)).json()["has_template"] is True


# ------------------------------------------------------------------ access


async def test_without_the_permission_the_offer_settings_are_not_reachable(client, auth_headers, staff_headers):
    internship, ids = await _ready(client, auth_headers)
    sid = ids["asha@example.com"]
    for method, url, kwargs in (
        ("get", f"{_INTERN}/{internship['id']}/offer", {}),
        ("put", f"{_INTERN}/{internship['id']}/offer/layout", {"json": {"fields": [NAME_FIELD]}}),
        ("put", f"{_INTERN}/{internship['id']}/offer/email", {"json": {"subject": "x"}}),
        ("get", f"{_INTERN}/{internship['id']}/offer/template", {}),
        ("post", f"{_INTERN}/{internship['id']}/offer/preview", {"json": {}}),
        ("post", f"{_INTERN}/{internship['id']}/offer/test-email", {"json": {"to_email": "a@example.com"}}),
        ("get", f"{_INTERN}/{internship['id']}/selected/{sid}/offer.pdf", {}),
        ("post", f"{_INTERN}/{internship['id']}/offers/release", {"json": {}}),
    ):
        r = await getattr(client, method)(url, headers=staff_headers, **kwargs)
        assert r.status_code == 403, (method, url, r.status_code)


async def test_another_organization_cannot_reach_or_release_these_offers(client, auth_headers, db_session, queued):
    internship, ids = await _ready(client, auth_headers)
    other = await OrganizationRepository(db_session).create(name="Rival Org", slug=f"rival-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other, is_superuser=True, email=f"rival-{uuid.uuid4().hex[:6]}@example.com")
    rival = {"Authorization": f"Bearer {token}"}
    for method, url, kwargs in (
        ("get", f"{_INTERN}/{internship['id']}/offer", {}),
        ("get", f"{_INTERN}/{internship['id']}/offer/template", {}),
        ("put", f"{_INTERN}/{internship['id']}/offer/email", {"json": {"subject": "x"}}),
        ("post", f"{_INTERN}/{internship['id']}/offers/release", {"json": {}}),
        ("get", f"{_INTERN}/{internship['id']}/selected/{ids['asha@example.com']}/offer.pdf", {}),
    ):
        assert (await getattr(client, method)(url, headers=rival, **kwargs)).status_code == 404, (method, url)
    assert queued == []
    assert (await db_session.execute(select(OurInternship.status).where(OurInternship.id == uuid.UUID(internship["id"])))).scalar_one().value == "selecting"
