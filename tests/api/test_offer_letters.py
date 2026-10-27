"""
The offer letter generator: settings that are saved once and reused (with per-internship overrides), uploaded branding images,
a previewed and approved design, bulk generation that survives one bad letter and never makes duplicates, approval, and the
separate, explicit release that emails each student only their own PDF.

What must hold: nothing is emailed until an administrator releases approved letters, one student's details never appear in
another's letter, missing details are reported instead of invented, a changed setting marks letters outdated, regenerating keeps
the old version, and only administrators can change anything official.
"""

import io
import uuid
import zipfile

import pytest
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import func, select

from modules.institutions.models import InstitutionStudent
from modules.our_internships import letter_routes, letter_tasks, letters
from modules.our_internships.letter_models import OfferLetter
from modules.our_internships.models import InternshipSelection, OfferStatus
from tests.api.test_internship_instructors import _assign, _instructor
from tests.api.test_internship_offers import _Mailbox, _setup
from tests.api.test_internship_learning import _world

pytestmark = pytest.mark.api

_INTERN = "/api/v1/our-internships"
COMPANY = {
    "name": "GIR Technologies", "address": "Ameerpet, Hyderabad", "phone": "+91 81438 94179", "email": "info@girtechnologies.com",
    "website": "www.girtechnologies.com", "signatory_name": "ATLURI SRUJAN", "signatory_designation": "CEO",
}
PROGRAMME = {
    "position": "Intern", "duration": "3 months", "start_date": "2026-03-13", "end_date": "2026-06-12",
    "phases": [{"label": "Month 1", "title": "Training & Skill Development"}, {"label": "Month 2", "title": "Project Work"}],
}


def png(color=(200, 30, 30, 255)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (120, 60), color).save(out, "PNG")
    return out.getvalue()


def url(internship, tail=""):
    return f"{_INTERN}/{internship['id']}/offer-letters{tail}"


def text_of(pdf: bytes) -> str:
    return " ".join(" ".join(p.extract_text().split()) for p in PdfReader(io.BytesIO(pdf)).pages)


async def configure(client, headers, internship, scope="internship", **sections):
    """Save the company and programme details (and any other sections given) the way the Configuration tab does."""
    config = (await client.get(url(internship), headers=headers)).json()["config"]
    config["company"].update(COMPANY)
    config["programme"].update(PROGRAMME)
    for name, values in sections.items():
        config[name].update(values)
    r = await client.put(url(internship, "/config"), json={"config": config, "scope": scope}, headers=headers)
    assert r.status_code == 200, r.text


async def approved(client, headers, internship, **sections):
    await configure(client, headers, internship, **sections)
    r = await client.post(url(internship, "/approve-design"), headers=headers)
    assert r.status_code == 200, r.text


@pytest.fixture
def world(monkeypatch, db_session):
    """Collects what would be queued and runs it on the test session, so nothing needs a message broker."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx():
        yield db_session

    monkeypatch.setattr(letter_tasks, "get_db_context", _ctx)
    box = _Mailbox()
    monkeypatch.setattr(letter_tasks.email_service, "send", box.send)
    monkeypatch.setattr(letters.email_service, "send", box.send)
    state = type("W", (), {"generation": [], "emails": [], "mail": box})()
    monkeypatch.setattr(letter_routes, "enqueue_generation", lambda ids: state.generation.append(list(ids)))
    monkeypatch.setattr(letter_routes, "enqueue_letter_emails", lambda ids: state.emails.append(list(ids)))
    return state


async def run_generation(world):
    while world.generation:
        await letter_tasks.generate_batch(world.generation.pop(0))


async def generate(client, headers, internship, world, **body):
    r = await client.post(url(internship, "/generate"), json=body, headers=headers)
    assert r.status_code == 200, r.text
    await run_generation(world)
    return r.json()


async def students(client, headers, internship):
    r = await client.get(url(internship, "/students"), headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def by_name(body):
    return {s["name"]: s for s in body["students"]}


async def another_internship(client, headers, ids=(), title="Another Programme"):
    """A second internship in the same organisation (the students already exist), with the given students selected."""
    internship = (await client.post(_INTERN, json={"title": title, "scope": "all"}, headers=headers)).json()
    if ids:
        r = await client.post(f"{_INTERN}/{internship['id']}/selected", json={"student_ids": list(ids)}, headers=headers)
        assert r.status_code == 200, r.text
    return internship


async def ready_world(client, headers, world, **sections):
    internship, ids = await _setup(client, headers)
    await approved(client, headers, internship, **sections)
    await generate(client, headers, internship, world)
    return internship, ids


# ------------------------------------------------------------ settings and images


async def test_a_new_internship_lists_what_is_missing_and_nothing_is_approved(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    s = (await client.get(url(internship), headers=auth_headers)).json()
    assert s["design_state"] == "not_approved" and s["has_overrides"] is False
    assert "Enter the company name." in s["problems"] and "Enter the internship start date." in s["problems"]
    assert s["config"]["content"]["financial_note"]["enabled"] is False  # nothing financial unless an admin adds it
    assert set(s["assets"]) == {"logo", "watermark", "signature", "stamp", "extra"} and not any(s["assets"].values())
    assert "student_name" in s["placeholders"]


async def test_settings_saved_as_defaults_are_reused_and_an_internship_can_override_part_of_them(client, auth_headers):
    first, _ = await _setup(client, auth_headers)
    await configure(client, auth_headers, first, scope="defaults")
    second = (await client.post(_INTERN, json={"title": "Second Programme", "scope": "all"}, headers=auth_headers)).json()
    s = (await client.get(url(second), headers=auth_headers)).json()
    assert s["config"]["company"]["name"] == "GIR Technologies" and s["config"]["programme"]["position"] == "Intern"
    assert s["has_overrides"] is False and s["problems"] == []
    config = s["config"]
    config["programme"]["position"] = "Analyst Intern"
    assert (await client.put(url(second, "/config"), json={"config": config}, headers=auth_headers)).status_code == 200
    s = (await client.get(url(second), headers=auth_headers)).json()
    assert s["has_overrides"] is True and s["config"]["programme"]["position"] == "Analyst Intern"
    assert s["defaults"]["programme"]["position"] == "Intern"
    # the first internship still follows the defaults, and a later change to them flows through to what was not overridden
    config["company"]["phone"] = "+91 99999 00000"
    await client.put(url(second, "/config"), json={"config": {**config, "programme": {**config["programme"], "position": "Intern"}}, "scope": "defaults"}, headers=auth_headers)
    s = (await client.get(url(second), headers=auth_headers)).json()
    assert s["config"]["company"]["phone"] == "+91 99999 00000"
    assert (await client.delete(url(second, "/config"), headers=auth_headers)).status_code == 200
    assert (await client.get(url(second), headers=auth_headers)).json()["has_overrides"] is False


async def test_text_the_letter_cannot_print_or_unknown_placeholders_are_refused(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    config = (await client.get(url(internship), headers=auth_headers)).json()["config"]
    config["content"]["closing"] = "Welcome {{nickname}}"
    bad = await client.put(url(internship, "/config"), json={"config": config}, headers=auth_headers)
    assert bad.status_code == 422 and "not recognised" in bad.text
    config["content"]["closing"] = "Fine."
    config["programme"].update({"start_date": "2026-06-01", "end_date": "2026-05-01"})
    assert (await client.put(url(internship, "/config"), json={"config": config}, headers=auth_headers)).status_code == 422


async def test_images_are_uploaded_replaced_and_overridden_per_internship(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    up = lambda kind, data, scope="internship", name="logo.png": client.put(  # noqa: E731
        url(internship, f"/assets/{kind}?scope={scope}"), files={"file": (name, data, "image/png")}, headers=auth_headers
    )
    assert (await up("logo", png(), "defaults")).status_code == 200
    s = (await client.get(url(internship), headers=auth_headers)).json()
    assert s["assets"]["logo"]["source"] == "defaults" and s["assets"]["logo"]["content_type"] == "image/png"
    assert (await up("logo", png((0, 0, 255, 255)))).status_code == 200  # this internship's own logo wins
    assert (await client.get(url(internship), headers=auth_headers)).json()["assets"]["logo"]["source"] == "internship"
    shown = await client.get(url(internship, "/assets/logo"), headers=auth_headers)
    assert shown.status_code == 200 and shown.headers["content-type"] == "image/png" and "sandbox" in shown.headers["content-security-policy"]
    assert (await client.delete(url(internship, "/assets/logo?scope=internship"), headers=auth_headers)).status_code == 200
    assert (await client.get(url(internship), headers=auth_headers)).json()["assets"]["logo"]["source"] == "defaults"
    assert (await client.delete(url(internship, "/assets/logo?scope=internship"), headers=auth_headers)).status_code == 404


async def test_only_real_images_can_be_uploaded(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    put = lambda kind, data: client.put(url(internship, f"/assets/{kind}"), files={"file": ("x", data, "image/png")}, headers=auth_headers)  # noqa: E731
    assert (await put("signature", b"%PDF-1.4 not an image")).status_code == 422
    assert (await put("signature", b"")).status_code == 422
    assert (await put("signature", b"x" * (4 * 1024 * 1024 + 10))).status_code == 422
    assert (await put("sticker", png())).status_code == 422
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'
    assert (await put("logo", svg)).status_code == 200


# ------------------------------------------------------------ preview and approval


async def test_the_preview_shows_a_sample_or_a_students_letter_from_the_settings_on_screen(client, auth_headers):
    internship, ids = await _setup(client, auth_headers)
    await configure(client, auth_headers, internship)
    sample = await client.post(url(internship, "/preview"), json={}, headers=auth_headers)
    assert sample.status_code == 200 and sample.headers["content-type"] == "application/pdf" and sample.headers["x-letter-sample"] == "1"
    assert "Asha Rao" in text_of(sample.content)
    config = (await client.get(url(internship), headers=auth_headers)).json()["config"]
    config["company"]["name"] = "Draft Co"  # not saved
    real = await client.post(url(internship, "/preview"), json={"student_id": ids["meera@example.com"], "config": config}, headers=auth_headers)
    text = text_of(real.content)
    assert real.headers["x-letter-sample"] == "0" and "Meera Iyer" in text and "Draft Co" in text and "Asha" not in text
    assert (await client.get(url(internship), headers=auth_headers)).json()["config"]["company"]["name"] == "GIR Technologies"


async def test_letters_need_complete_settings_and_an_approved_design_and_any_change_undoes_the_approval(client, auth_headers, world):
    internship, _ = await _setup(client, auth_headers)
    r = await client.post(url(internship, "/generate"), json={}, headers=auth_headers)
    assert r.status_code == 422 and "Finish the settings" in r.text
    assert (await client.post(url(internship, "/approve-design"), headers=auth_headers)).status_code == 422
    await configure(client, auth_headers, internship)
    r = await client.post(url(internship, "/generate"), json={}, headers=auth_headers)
    assert r.status_code == 422 and "Approve the letter design" in r.text
    assert (await client.post(url(internship, "/approve-design"), headers=auth_headers)).status_code == 200
    assert (await client.get(url(internship), headers=auth_headers)).json()["design_state"] == "approved"
    assert (await client.put(url(internship, "/assets/signature"), files={"file": ("sig.png", png(), "image/png")}, headers=auth_headers)).status_code == 200
    assert (await client.get(url(internship), headers=auth_headers)).json()["design_state"] == "changed"
    r = await client.post(url(internship, "/generate"), json={}, headers=auth_headers)
    assert r.status_code == 422 and "approve the design again" in r.text
    assert world.generation == []


async def test_the_financial_note_must_be_approved_before_a_design_can_be(client, auth_headers):
    internship, _ = await _setup(client, auth_headers)
    await configure(client, auth_headers, internship, content={"financial_note": {"enabled": True, "approved": False, "amount": "INR 2,000/-"}})
    r = await client.post(url(internship, "/approve-design"), headers=auth_headers)
    assert r.status_code == 422 and "not approved" in r.text


# ------------------------------------------------------------ generating


async def test_every_selected_student_gets_their_own_letter_with_a_reference_and_a_safe_file_name(client, auth_headers, world):
    internship, _ = await ready_world(client, auth_headers, world)
    body = await students(client, auth_headers, internship)
    assert body["counts"]["ready"] == 3 and body["in_progress"] == 0
    rows = by_name(body)
    refs = {r["letter"]["reference"] for r in rows.values()}
    assert len(refs) == 3 and all(r.startswith("OFR-") for r in refs)
    for name, other in (("Asha Rao", "Meera"), ("Meera Iyer", "Ravi"), ("Ravi Kumar", "Asha")):
        letter = rows[name]["letter"]
        assert letter["status"] == "ready" and letter["version"] == 1 and letter["page_count"] == 2
        assert letter["filename"].startswith("OfferLetter_") and letter["filename"].endswith(".pdf") and " " not in letter["filename"]
        pdf = (await client.get(url(internship, f"/letters/{letter['id']}/pdf"), headers=auth_headers)).content
        text = text_of(pdf)
        assert "Sri Venkateswara College" in text and "Tirupati" in text and "Position: Intern" in text and "GIR Technologies" in text
        assert name in text and other not in text  # one student's details never appear in another's letter


async def test_asking_to_generate_twice_does_not_make_duplicates(client, auth_headers, world, db_session):
    internship, ids = await ready_world(client, auth_headers, world)
    again = await generate(client, auth_headers, internship, world)
    assert again["queued"] == 0 and again["already_generated"] == 3
    count = (await db_session.execute(select(func.count()).select_from(OfferLetter))).scalar_one()
    assert count == 3
    # two requests while the first is still waiting for the worker
    internship2 = await another_internship(client, auth_headers, ids.values())
    await approved(client, auth_headers, internship2)
    one = (await client.post(url(internship2, "/generate"), json={}, headers=auth_headers)).json()
    two = (await client.post(url(internship2, "/generate"), json={}, headers=auth_headers)).json()
    assert one["queued"] == 3 and two["queued"] == 0 and two["in_progress"] == 3
    assert (await students(client, auth_headers, internship2))["counts"]["pending"] == 3


async def test_if_the_queue_is_unreachable_the_letters_can_be_generated_again_and_a_lost_task_is_retried(client, auth_headers, world, monkeypatch, db_session):
    from datetime import datetime, timedelta, timezone

    internship, _ = await _setup(client, auth_headers)
    await approved(client, auth_headers, internship)

    def broker_down(ids):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(letter_routes, "enqueue_generation", broker_down)
    r = await client.post(url(internship, "/generate"), json={}, headers=auth_headers)
    assert r.status_code == 503
    body = await students(client, auth_headers, internship)
    assert body["counts"]["failed"] == 3 and body["in_progress"] == 0  # not stuck waiting for a task that never started
    assert "could not be queued" in body["students"][0]["letter"]["error"]
    monkeypatch.setattr(letter_routes, "enqueue_generation", lambda ids: world.generation.append(list(ids)))
    again = await generate(client, auth_headers, internship, world)
    assert again["queued"] == 3 and (await students(client, auth_headers, internship))["counts"]["ready"] == 3
    assert (await db_session.execute(select(func.count()).select_from(OfferLetter))).scalar_one() == 3  # the same rows, no duplicates

    # a letter whose background task was lost (still waiting long after) is picked up by the next Generate
    other = await another_internship(client, auth_headers, [s["student_id"] for s in body["students"]], "Stuck Programme")
    await approved(client, auth_headers, other)
    await client.post(url(other, "/generate"), json={}, headers=auth_headers)  # queued but never run
    assert (await client.post(url(other, "/generate"), json={}, headers=auth_headers)).json()["in_progress"] == 3
    rows = (await db_session.execute(select(OfferLetter).where(OfferLetter.internship_id == uuid.UUID(other["id"])))).scalars().all()
    for row in rows:
        row.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.flush()
    retry = await client.post(url(other, "/generate"), json={}, headers=auth_headers)
    assert retry.json()["queued"] == 3


async def test_students_with_missing_details_are_flagged_and_do_not_stop_the_others(client, auth_headers, world, db_session):
    internship, ids = await _setup(client, auth_headers)
    student = await db_session.get(InstitutionStudent, ids["ravi@example.com"])
    student.email = ""
    other = await db_session.get(InstitutionStudent, ids["meera@example.com"])
    other.name = "आशा"  # a name the letter's fonts cannot print
    await db_session.flush()
    await approved(client, auth_headers, internship)
    body = await students(client, auth_headers, internship)
    rows = by_name(body)
    assert rows["Ravi Kumar"]["status"] == "missing_data" and rows["आशा"]["status"] == "missing_data"
    result = await generate(client, auth_headers, internship, world)
    assert result["queued"] == 1 and len(result["blocked"]) == 2 and "need their details fixed" in result["message"]
    reasons = " ".join(i for b in result["blocked"] for i in b["issues"])
    assert "email address is missing" in reasons and "cannot print" in reasons
    after = await students(client, auth_headers, internship)
    assert after["counts"]["ready"] == 1 and after["counts"]["missing_data"] == 2
    # fixing the details and generating again makes only the missing letters
    student.email = "ravi@example.com"
    other.name = "Meera Iyer"
    await db_session.flush()
    again = await generate(client, auth_headers, internship, world)
    assert again["queued"] == 2 and again["already_generated"] == 1 and again["blocked"] == []
    assert (await students(client, auth_headers, internship))["counts"]["ready"] == 3


async def test_a_letter_that_fails_is_recorded_and_the_others_are_still_made(client, auth_headers, world, monkeypatch):
    internship, _ = await _setup(client, auth_headers)
    await approved(client, auth_headers, internship)
    real = letters.build_letter_pdf

    def flaky(config, facts, *args, **kwargs):
        if facts.name == "Meera Iyer":
            raise RuntimeError("the renderer broke")
        return real(config, facts, *args, **kwargs)

    monkeypatch.setattr(letters, "build_letter_pdf", flaky)
    await generate(client, auth_headers, internship, world)
    rows = by_name(await students(client, auth_headers, internship))
    assert rows["Meera Iyer"]["status"] == "failed" and "the renderer broke" in rows["Meera Iyer"]["letter"]["error"]
    assert rows["Asha Rao"]["status"] == rows["Ravi Kumar"]["status"] == "ready"
    monkeypatch.setattr(letters, "build_letter_pdf", real)
    retry = await generate(client, auth_headers, internship, world)  # the failed one is tried again, the others left alone
    assert retry["queued"] == 1 and retry["already_generated"] == 2
    assert by_name(await students(client, auth_headers, internship))["Meera Iyer"]["status"] == "ready"


async def test_a_sample_letter_of_many_pages_and_optional_sections_is_made_for_every_student(client, auth_headers, world):
    terms = [f"Clause {i}: " + "The intern agrees to follow the rules of the programme. " * 6 for i in range(1, 25)]
    internship, _ = await _setup(client, auth_headers)
    await approved(client, auth_headers, internship, content={"terms": terms, "guardian_required": True, "notes": ["Keep this letter safe."]})
    await generate(client, auth_headers, internship, world)
    for row in (await students(client, auth_headers, internship))["students"]:
        assert row["letter"]["page_count"] >= 3 and row["letter"]["status"] == "ready"
    pdf = (await client.get(url(internship, f"/letters/{row['letter']['id']}/pdf"), headers=auth_headers)).content
    text = text_of(pdf)
    assert "Clause 24:" in text and "Signature of Parent/Guardian:" in text and "Keep this letter safe." in text


async def test_no_signature_is_ever_drawn_unless_one_was_uploaded(client, auth_headers, world):
    internship, _ = await ready_world(client, auth_headers, world)
    letter = by_name(await students(client, auth_headers, internship))["Asha Rao"]["letter"]
    pdf = (await client.get(url(internship, f"/letters/{letter['id']}/pdf"), headers=auth_headers)).content
    assert all(len(p.images) == 0 for p in PdfReader(io.BytesIO(pdf)).pages)
    assert "ATLURI SRUJAN" in text_of(pdf)  # the printed name and designation only


async def test_the_uploaded_signature_and_branding_are_used_on_every_letter(client, auth_headers, world):
    internship, _ = await _setup(client, auth_headers)
    for kind, colour in (("logo", (200, 30, 30, 255)), ("watermark", (30, 200, 30, 255)), ("signature", (30, 30, 200, 255))):
        r = await client.put(url(internship, f"/assets/{kind}"), files={"file": (f"{kind}.png", png(colour), "image/png")}, headers=auth_headers)
        assert r.status_code == 200
    await approved(client, auth_headers, internship)
    await generate(client, auth_headers, internship, world)
    for row in (await students(client, auth_headers, internship))["students"]:
        pdf = (await client.get(url(internship, f"/letters/{row['letter']['id']}/pdf"), headers=auth_headers)).content
        pages = PdfReader(io.BytesIO(pdf)).pages
        assert len(pages[0].images) == 2 and len(pages[1].images) == 3  # logo+watermark, then watermark+signature+small logo


async def test_the_letters_can_be_downloaded_one_by_one_and_together(client, auth_headers, world):
    internship, _ = await ready_world(client, auth_headers, world)
    rows = (await students(client, auth_headers, internship))["students"]
    one = await client.get(url(internship, f"/letters/{rows[0]['letter']['id']}/pdf?download=true"), headers=auth_headers)
    assert one.status_code == 200 and one.headers["content-disposition"].startswith("attachment") and one.content.startswith(b"%PDF")
    everything = await client.get(url(internship, "/download.zip"), headers=auth_headers)
    assert everything.status_code == 200 and everything.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(everything.content)).namelist()
    assert len(names) == 3 and all(n.startswith("OfferLetter_") and n.endswith(".pdf") for n in names)
    chosen = await client.get(url(internship, f"/download.zip?letter_id={rows[1]['letter']['id']}"), headers=auth_headers)
    assert len(zipfile.ZipFile(io.BytesIO(chosen.content)).namelist()) == 1
    empty = await another_internship(client, auth_headers)
    assert (await client.get(url(empty, "/download.zip"), headers=auth_headers)).status_code == 422


# ------------------------------------------------------------ approving and releasing


async def test_nothing_is_emailed_by_generating_or_approving_only_by_releasing_approved_letters(client, auth_headers, world, db_session):
    internship, _ = await ready_world(client, auth_headers, world)
    assert world.mail.sent == [] and world.emails == []
    rows = by_name(await students(client, auth_headers, internship))
    asha, meera = rows["Asha Rao"]["letter"]["id"], rows["Meera Iyer"]["letter"]["id"]
    # a letter that was not approved cannot be released
    r = (await client.post(url(internship, "/release"), json={"letter_ids": [asha]}, headers=auth_headers)).json()
    assert r["queued"] == 0 and "Approve the letter first" in r["skipped"][0]["reason"] and world.emails == []
    approve = await client.post(url(internship, "/approve"), json={"letter_ids": [asha, meera]}, headers=auth_headers)
    assert approve.json()["message"].startswith("Approved 2 letters")
    assert world.mail.sent == []
    r = (await client.post(url(internship, "/release"), json={"letter_ids": [asha]}, headers=auth_headers)).json()
    assert r["queued"] == 1 and len(world.emails) == 1 and len(world.emails[0]) == 1
    await letter_tasks._send_letter(uuid.UUID(asha))
    assert len(world.mail.sent) == 1  # only Asha's, Meera's is approved but not released
    mail = world.mail.sent[0]
    assert mail["to"] == "asha@example.com" and "GIR Technologies" in mail["subject"] and "Dear Asha Rao" in mail["text"]
    attachment = mail["attachments"][0]
    assert attachment.mime_type == "application/pdf" and attachment.filename.startswith("OfferLetter_") and "Asha Rao" in text_of(attachment.content)
    assert "Meera" not in text_of(attachment.content)
    rows = by_name(await students(client, auth_headers, internship))
    assert rows["Asha Rao"]["letter"]["status"] == "released" and rows["Asha Rao"]["letter"]["sent_to_email"] == "asha@example.com"
    assert rows["Meera Iyer"]["letter"]["status"] == "approved" and rows["Meera Iyer"]["letter"]["delivery_status"] == "none"
    selection = (await db_session.execute(select(InternshipSelection).where(InternshipSelection.offer_reference == rows["Asha Rao"]["letter"]["reference"]))).scalar_one()
    assert selection.offer_status == OfferStatus.SENT and selection.offer_sent_at is not None
    sends = (await client.get(url(internship, "/deliveries"), headers=auth_headers)).json()
    assert [(d["student_name"], d["status"], d["attempt"]) for d in sends] == [("Asha Rao", "sent", 1)]
    # releasing the same letter again sends nothing unless asked to resend
    again = (await client.post(url(internship, "/release"), json={"letter_ids": [asha]}, headers=auth_headers)).json()
    assert again["queued"] == 0 and again["skipped"][0]["reason"] == "Already sent."
    # a duplicate background task does not send a second email
    await letter_tasks._send_letter(uuid.UUID(asha))
    assert len(world.mail.sent) == 1


async def test_a_failed_send_is_retried_then_recorded_with_its_reason_and_can_be_released_again(client, auth_headers, world):
    internship, _ = await ready_world(client, auth_headers, world)
    asha = by_name(await students(client, auth_headers, internship))["Asha Rao"]["letter"]["id"]
    await client.post(url(internship, "/approve"), json={"letter_ids": [asha]}, headers=auth_headers)
    await client.post(url(internship, "/release"), json={"letter_ids": [asha]}, headers=auth_headers)
    world.mail.ok = False
    letter_id = uuid.UUID(asha)
    for attempt in range(1, letter_tasks.MAX_ATTEMPTS):
        assert await letter_tasks._send_letter(letter_id) is False  # try again later
    assert await letter_tasks._send_letter(letter_id) is True  # out of attempts
    row = by_name(await students(client, auth_headers, internship))["Asha Rao"]["letter"]
    assert row["delivery_status"] == "failed" and row["status"] == "approved" and "could not be delivered" in row["delivery_error"]
    history = (await client.get(url(internship, "/deliveries"), headers=auth_headers)).json()
    assert [d["status"] for d in history] == ["failed"] * letter_tasks.MAX_ATTEMPTS and history[0]["attempt"] == letter_tasks.MAX_ATTEMPTS
    world.mail.ok = True
    r = (await client.post(url(internship, "/release"), json={"letter_ids": [asha]}, headers=auth_headers)).json()
    assert r["queued"] == 1
    assert await letter_tasks._send_letter(letter_id) is True
    assert by_name(await students(client, auth_headers, internship))["Asha Rao"]["letter"]["status"] == "released"
    actions = [e["action"] for e in (await client.get(url(internship, "/events"), headers=auth_headers)).json()]
    assert "letter_send_failed" in actions and "letter_sent" in actions and "release_requested" in actions


async def test_if_the_queue_is_unreachable_nothing_is_marked_as_sending(client, auth_headers, world, monkeypatch):
    internship, _ = await ready_world(client, auth_headers, world)
    asha = by_name(await students(client, auth_headers, internship))["Asha Rao"]["letter"]["id"]
    await client.post(url(internship, "/approve"), json={"letter_ids": [asha]}, headers=auth_headers)

    def broker_down(ids):
        raise ConnectionError("redis is down")

    monkeypatch.setattr(letter_routes, "enqueue_letter_emails", broker_down)
    r = await client.post(url(internship, "/release"), json={"letter_ids": [asha]}, headers=auth_headers)
    assert r.status_code == 503 and "Nothing was sent" in r.text
    assert by_name(await students(client, auth_headers, internship))["Asha Rao"]["letter"]["delivery_status"] == "none"


async def test_the_email_can_be_previewed_and_a_test_sent_before_anything_is_released(client, auth_headers, world):
    internship, ids = await ready_world(client, auth_headers, world, email={"subject": "Offer for {{student_name}}", "body": "Hi {{student_name}} at {{institution_name}}: {{internship_position}} from {{internship_start_date}}"})
    preview = (await client.post(url(internship, "/email-preview"), json={"student_id": ids["ravi@example.com"]}, headers=auth_headers)).json()
    assert preview["to"] == "ravi@example.com" and preview["subject"] == "Offer for Ravi Kumar"
    assert preview["body"] == "Hi Ravi Kumar at Sri Venkateswara College: Intern from 13-03-2026" and preview["attachment"].startswith("OfferLetter_")
    sent = await client.post(url(internship, "/test-email"), json={"to_email": "me@example.com"}, headers=auth_headers)
    assert sent.status_code == 200 and world.mail.sent[0]["to"] == "me@example.com" and world.mail.sent[0]["subject"].startswith("[Test]")
    assert world.mail.sent[0]["attachments"][0].filename == "OfferLetter_Sample.pdf"
    assert len(world.mail.sent) == 1 and world.emails == []


# ------------------------------------------------------------ changes and regeneration


async def test_a_changed_setting_marks_letters_outdated_and_regenerating_keeps_the_old_version(client, auth_headers, world):
    internship, _ = await ready_world(client, auth_headers, world)
    rows = by_name(await students(client, auth_headers, internship))
    asha = rows["Asha Rao"]["letter"]
    await client.post(url(internship, "/approve"), json={"letter_ids": [asha["id"]]}, headers=auth_headers)
    await client.post(url(internship, "/release"), json={"letter_ids": [asha["id"]]}, headers=auth_headers)
    await letter_tasks._send_letter(uuid.UUID(asha["id"]))
    sent_before = len(world.mail.sent)

    await approved(client, auth_headers, internship, programme={"position": "Security Analyst Intern"})
    rows = by_name(await students(client, auth_headers, internship))
    assert all(r["letter"]["outdated"] for r in rows.values())
    # an outdated letter cannot be approved or released
    assert "could not be approved" in (await client.post(url(internship, "/approve"), json={"letter_ids": [rows["Meera Iyer"]["letter"]["id"]]}, headers=auth_headers)).json()["message"]
    skipped = (await client.post(url(internship, "/release"), json={"letter_ids": [asha["id"]], "resend": True}, headers=auth_headers)).json()
    assert skipped["queued"] == 0 and "outdated" in skipped["skipped"][0]["reason"]
    # plain "generate" never redoes letters on its own
    assert (await generate(client, auth_headers, internship, world))["queued"] == 0
    redo = await generate(client, auth_headers, internship, world, regenerate=True)
    assert redo["queued"] == 3
    rows = by_name(await students(client, auth_headers, internship))
    new = rows["Asha Rao"]["letter"]
    assert new["version"] == 2 and new["status"] == "ready" and new["outdated"] is False and new["reference"] == asha["reference"]
    assert new["delivery_status"] == "none"  # the new version is not sent automatically
    assert len(world.mail.sent) == sent_before
    versions = (await client.get(url(internship, f"/students/{rows['Asha Rao']['student_id']}/versions"), headers=auth_headers)).json()
    assert [(v["version"], v["status"]) for v in versions] == [(2, "ready"), (1, "released")]
    old_pdf = (await client.get(url(internship, f"/letters/{asha['id']}/pdf"), headers=auth_headers)).content
    new_pdf = (await client.get(url(internship, f"/letters/{new['id']}/pdf"), headers=auth_headers)).content
    assert "Position: Intern" in text_of(old_pdf) and "Position: Security Analyst Intern" in text_of(new_pdf)
    assert new["filename"].endswith("_v2.pdf")


async def test_a_correction_to_one_students_details_outdates_only_that_letter(client, auth_headers, world, db_session):
    internship, ids = await ready_world(client, auth_headers, world)
    student = await db_session.get(InstitutionStudent, ids["meera@example.com"])
    student.name = "Meera R. Iyer"
    await db_session.flush()
    rows = by_name(await students(client, auth_headers, internship))
    assert rows["Meera R. Iyer"]["letter"]["outdated"] is True
    assert rows["Asha Rao"]["letter"]["outdated"] is False and rows["Ravi Kumar"]["letter"]["outdated"] is False
    redo = await generate(client, auth_headers, internship, world, student_ids=[ids["meera@example.com"]], regenerate=True)
    assert redo["queued"] == 1
    new = by_name(await students(client, auth_headers, internship))["Meera R. Iyer"]["letter"]
    pdf = (await client.get(url(internship, f"/letters/{new['id']}/pdf"), headers=auth_headers)).content
    assert new["version"] == 2 and "Meera R. Iyer" in text_of(pdf)


async def test_only_students_on_the_selected_list_can_have_a_letter(client, auth_headers, world):
    internship, ids = await _setup(client, auth_headers, select_emails=("asha@example.com",))
    await approved(client, auth_headers, internship)
    r = await client.post(url(internship, "/generate"), json={"student_ids": [ids["ravi@example.com"]]}, headers=auth_headers)
    assert r.status_code == 422 and "selected list" in r.text
    empty = await another_internship(client, auth_headers)
    await approved(client, auth_headers, empty)
    assert (await client.post(url(empty, "/generate"), json={}, headers=auth_headers)).status_code == 422


# ------------------------------------------------------------ who may do what


async def test_instructors_can_look_at_letters_but_only_administrators_change_anything_official(client, auth_headers, db_session, organization, world):
    internship, _ = await _world(client, auth_headers, db_session, organization)
    trainer, headers = await _instructor(client, db_session, organization)
    other_internship = await another_internship(client, auth_headers)
    await _assign(client, auth_headers, internship, trainer)
    assert (await client.get(url(internship), headers=headers)).status_code == 200
    assert (await client.get(url(internship, "/students"), headers=headers)).status_code == 200
    assert (await client.post(url(internship, "/preview"), json={}, headers=headers)).status_code == 200
    config = (await client.get(url(internship), headers=headers)).json()["config"]
    assert (await client.put(url(internship, "/config"), json={"config": config}, headers=headers)).status_code == 403
    assert (await client.put(url(internship, "/assets/signature"), files={"file": ("s.png", png(), "image/png")}, headers=headers)).status_code == 403
    assert (await client.get(url(internship, "/assets/signature"), headers=headers)).status_code == 403
    for tail, body in (("/approve-design", None), ("/generate", {}), ("/approve", {}), ("/release", {"letter_ids": ["00000000-0000-0000-0000-000000000000"]})):
        r = await client.post(url(internship, tail), json=body, headers=headers)
        assert r.status_code == 403, tail
    assert (await client.delete(url(internship, "/config"), headers=headers)).status_code == 403
    # and an internship they were not assigned to stays closed
    assert (await client.get(url(other_internship), headers=headers)).status_code == 403
    assert world.generation == [] and world.emails == []
