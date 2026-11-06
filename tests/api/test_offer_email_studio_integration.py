"""
Offer letters x Email Studio, as an administrator uses them: the summary of the assigned template, an accurate HTML preview, a safe
test email, the two branded built-in templates (offer letter with an onboarding link, onboarding invitation), and the legacy email
when nothing is assigned. The safety rules underneath (pending links, leases, pinning) are tested in test_offer_email_token_safety.py
and test_offer_email_crash_recovery.py; these tests only add what the integration itself promises.
"""

import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest

from modules.email_studio.models import EmailStudioTemplate
from modules.internship_onboarding import emails as onboarding_emails
from modules.internship_onboarding.emails import PREVIEW_TOKEN
from modules.internship_onboarding.service import ApplicationService
from modules.our_internships.models import OurInternship
from tests.api.test_email_studio import _S, assign, publish
from tests.api.test_offer_email_token_safety import (  # noqa: F401 - fixtures and helpers shared with the other tests
    application_of,
    counts,
    give_link,
    mail,
    release,
    selection_of,
    send,
    setup,
    token_of,
    where_is,
)
from tests.api.test_offer_letters import url, world  # noqa: F401 - a fixture

pytestmark = pytest.mark.api

OFFER_KEY, INVITE_KEY = "internship_offer_letter", "internship_onboarding_invitation"


async def built_in(client, headers, code_key, erpx_key, name, props=None, assign_it=True):
    """A template made from one of the approved React Email designs, published and (by default) assigned to an ERPX email."""
    body = {"name": name, "source_type": "code", "category": "Internship Offer Letters", "code_template_key": code_key, "code_props": props or {}}
    r = await client.post(f"{_S}/templates", json=body, headers=headers)
    assert r.status_code == 201, r.text
    template = r.json()
    await publish(client, headers, template)
    if assign_it:
        await assign(client, headers, erpx_key, template["id"])
    return template


CTA_PARTS = ("Next step: complete your onboarding", "Confirm your details, upload your documents", "Start onboarding", "Your onboarding link is personal", "data-optional-for")


def assert_no_onboarding_call_to_action(email: dict) -> None:
    """Nothing of the optional onboarding section is left, in the HTML or the plain text: no heading, no sentence about a link or a
    deadline, no button or leftover label, no marker."""
    for part in CTA_PARTS:
        assert part not in email["html"], f"{part!r} is still in the HTML"
        assert part not in email["text"], f"{part!r} is still in the plain text"
    assert not re.search(r"<a\b(?![^>]*\bhref=)", email["html"]) and 'href=""' not in email["html"] and "{{" not in email["html"]


async def preview(kit, student=None):
    r = await kit.client.post(url(kit.internship, "/email-preview"), json={"student_id": kit.ids[student] if student else None}, headers=kit.headers)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------ the summary of what the email is made from


async def test_with_no_template_assigned_the_summary_says_the_legacy_email_is_used_and_it_still_previews(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None)
    got = await preview(kit)
    assert got["source"] == "legacy" and got["template"] is None and got["problem"] is None
    assert got["uses_link"] is False and got["subject"] and "<" in got["html"] and got["attachment"] == "OfferLetter_Sample.pdf"
    await release(kit)  # and the legacy email is still what gets sent
    assert await send(kit) is True and len(mail.sent) == 1 and mail.sent[0]["subject"] and len(mail.sent[0]["attachments"]) == 1


async def test_the_summary_names_the_published_template_and_version_and_the_html_is_what_will_be_sent(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None)
    template = await built_in(client, auth_headers, "internship_offer_onboarding", OFFER_KEY, "Offer with onboarding")
    got = await preview(kit, "asha@example.com")
    assert got["source"] == "studio" and got["problem"] is None
    assert got["template"]["name"] == "Offer with onboarding" and got["template"]["id"] == template["id"] and got["template"]["version_number"] == 1
    assert got["uses_link"] is True and got["link_available"] is True
    assert "Asha Rao" in got["html"] and "OfferLetter" in got["attachment"]
    # the preview shows a link that opens nothing
    assert PREVIEW_TOKEN in got["html"]
    await release(kit, link_policy="replace")
    assert await send(kit) is True
    sent = mail.sent[0]
    assert sent["subject"] == got["subject"] and "Asha Rao" in sent["html"] and "Start onboarding" in sent["html"]
    # same design, same text; only the sample link was swapped for the student's own
    assert sent["html"].replace(token_of(sent), PREVIEW_TOKEN) == got["html"]


async def test_publishing_a_newer_version_moves_the_summary_but_not_a_batch_already_released(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None, who=("asha", "meera"))
    template = await built_in(client, auth_headers, "internship_offer_onboarding", OFFER_KEY, "Offer with onboarding", {"heading": "First wording, {{student_name}}"})
    await release(kit, ("asha", "meera"))
    draft = (await client.get(f"{_S}/templates/{template['id']}", headers=auth_headers)).json()["current"]
    draft["code_props"] = {**draft["code_props"], "heading": "Second wording, {{student_name}}"}
    saved = await client.put(f"{_S}/templates/{template['id']}/draft", json={k: draft[k] for k in ("subject", "preheader", "code_template_key", "code_props", "brand_profile_id", "signature_id", "config") if k in draft}, headers=auth_headers)
    assert saved.status_code == 200, saved.text
    await publish(client, auth_headers, template)
    now = await preview(kit)
    assert now["template"]["version_number"] == 2 and "Second wording" in now["html"]
    await send(kit, "asha")
    await send(kit, "meera")
    assert all("First wording" in m["html"] and "Second wording" not in m["html"] for m in mail.sent)  # the release pinned version 1


async def test_an_assigned_template_that_stopped_working_is_reported_not_replaced(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None)
    template = await built_in(client, auth_headers, "internship_offer_onboarding", OFFER_KEY, "Offer with onboarding")
    row = await db_session.get(EmailStudioTemplate, uuid.UUID(template["id"]))
    row.deleted_at = datetime.now(timezone.utc)
    await db_session.flush()
    got = await preview(kit)
    assert got["source"] == "studio" and got["problem"] and "was deleted" in got["problem"] and got["subject"] == "(cannot be made)" and got["html"] == ""
    refused = await kit.client.post(url(kit.internship, "/release"), json={"letter_ids": [kit.letters["asha"]]}, headers=auth_headers)
    assert refused.status_code == 422 and mail.sent == []  # nothing is queued and no other wording is sent


# ------------------------------------------------------------ previews and tests are safe


async def test_previews_and_test_emails_leave_every_real_link_alone(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None)
    await built_in(client, auth_headers, "internship_offer_onboarding", OFFER_KEY, "Offer with onboarding")
    mine = await give_link(db_session, kit, "asha")
    before = await counts(db_session)
    app_before = await application_of(db_session, kit, "asha")
    hashes = (app_before.token_hash, app_before.token_issued_at, app_before.pending_token_hash)
    for student in (None, "asha@example.com", "meera@example.com"):
        got = await preview(kit, student)
        assert mine not in got["html"] and mine not in got["body"] and PREVIEW_TOKEN in got["html"]
    assert (await client.post(url(kit.internship, "/test-email"), json={"to_email": "me@example.com"}, headers=auth_headers)).status_code == 200
    sent = mail.sent[0]
    assert sent["subject"].startswith("[Test] ") and "This is a test email" in sent["html"] and "This is a test email" in sent["text"]
    assert PREVIEW_TOKEN in sent["html"] and mine not in sent["html"] and len(sent["attachments"]) == 1
    assert await counts(db_session) == before
    app_after = await application_of(db_session, kit, "asha")
    assert (app_after.token_hash, app_after.token_issued_at, app_after.pending_token_hash) == hashes and where_is(app_after, mine) == "active"
    assert await application_of(db_session, kit, "meera") is None  # nothing was created for a student who had no application


async def test_test_emails_have_the_same_hourly_limit_as_email_studio(client, auth_headers, world, mail, db_session, monkeypatch):  # noqa: F811
    from modules.email_studio import service as studio_service

    kit = await setup(client, auth_headers, world, html=None)
    monkeypatch.setattr(studio_service, "TEST_SENDS_PER_HOUR", 1)
    studio_service._recent_tests.clear()
    assert (await client.post(url(kit.internship, "/test-email"), json={"to_email": "me@example.com"}, headers=auth_headers)).status_code == 200
    assert (await client.post(url(kit.internship, "/test-email"), json={"to_email": "me@example.com"}, headers=auth_headers)).status_code == 429
    assert len(mail.sent) == 1
    studio_service._recent_tests.clear()


# ------------------------------------------------------------ the branded offer-letter design with the onboarding link


async def test_the_branded_offer_design_carries_the_personal_link_and_only_the_students_own_letter(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None, who=("asha", "meera"))
    await built_in(client, auth_headers, "internship_offer_onboarding", OFFER_KEY, "Offer with onboarding")
    await release(kit, ("asha", "meera"), link_policy="replace")
    await send(kit, "asha")
    await send(kit, "meera")
    first, second = mail.sent
    for mail_, name in ((first, "Asha"), (second, "Meera")):
        assert len(mail_["attachments"]) == 1 and mail_["attachments"][0].mime_type == "application/pdf"
        assert re.search(rf'<a[^>]+href="[^"]+#t={re.escape(token_of(mail_))}"', mail_["html"]) and name in mail_["html"]
    assert token_of(first) != token_of(second) and first["attachments"][0].content != second["attachments"][0].content
    asha = await application_of(db_session, kit, "asha")
    assert where_is(asha, token_of(first)) == "active" and where_is(asha, token_of(second)) == "dead"


async def test_a_student_with_a_link_keeps_it_by_default_and_the_design_leaves_the_button_out(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None)
    await built_in(client, auth_headers, "internship_offer_onboarding", OFFER_KEY, "Offer with onboarding")
    mine = await give_link(db_session, kit, "asha")
    await release(kit)  # link_policy defaults to keep_existing
    await send(kit)
    html = mail.sent[0]["html"]
    assert token_of(mail.sent[0]) is None and 'href=""' not in html and "#t=" not in html
    assert_no_onboarding_call_to_action(mail.sent[0])
    assert "Congratulations, Asha Rao" in html and "Internship" in html and "attached to this email" in html  # the rest of the email stays
    assert where_is(await application_of(db_session, kit, "asha"), mine) == "active"


async def test_in_manual_onboarding_the_branded_design_has_no_link_and_creates_nothing(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None, mode="manual")
    await built_in(client, auth_headers, "internship_offer_onboarding", OFFER_KEY, "Offer with onboarding")
    before = await counts(db_session)
    got = await preview(kit)
    assert got["link_available"] is False and "#t=" not in got["html"] and 'href=""' not in got["html"]
    assert_no_onboarding_call_to_action({"html": got["html"], "text": got["body"]})
    await release(kit)
    await send(kit)
    assert "#t=" not in mail.sent[0]["html"] and await counts(db_session) == before and await application_of(db_session, kit, "asha") is None
    assert_no_onboarding_call_to_action(mail.sent[0])


async def test_with_a_link_the_onboarding_call_to_action_is_there_exactly_once(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None)
    await built_in(client, auth_headers, "internship_offer_onboarding", OFFER_KEY, "Offer with onboarding")
    await release(kit, link_policy="replace")
    await send(kit)
    sent = mail.sent[0]
    for part in CTA_PARTS[:4]:
        assert sent["html"].count(part) == 1 and part in sent["text"], part
    assert len(re.findall(r'<a[^>]+href="[^"]+#t=', sent["html"])) == 1


async def test_a_student_the_batch_gives_a_link_and_one_who_keeps_theirs_get_the_matching_email(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None, who=("asha", "meera"))
    await built_in(client, auth_headers, "internship_offer_onboarding", OFFER_KEY, "Offer with onboarding")
    await give_link(db_session, kit, "asha")  # Asha already has a link; Meera does not
    await release(kit, ("asha", "meera"))
    await send(kit, "asha")
    await send(kit, "meera")
    asha, meera = mail.sent
    assert_no_onboarding_call_to_action(asha)
    assert "Start onboarding" in meera["html"] and token_of(meera) and "Next step: complete your onboarding" in meera["text"]


async def test_the_branded_offer_design_without_the_link_still_works_for_existing_setups(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None)
    await built_in(client, auth_headers, "internship_offer", OFFER_KEY, "Plain offer")
    got = await preview(kit)
    assert got["source"] == "studio" and got["uses_link"] is False
    await release(kit)
    await send(kit)
    assert len(mail.sent) == 1 and token_of(mail.sent[0]) is None and await application_of(db_session, kit, "asha") is None


# ------------------------------------------------------------ the separate invitation workflow


async def test_the_branded_invitation_design_is_sent_by_the_invitation_workflow_and_replaces_the_link_as_before(client, auth_headers, world, mail, db_session, monkeypatch):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=None)

    @asynccontextmanager
    async def _ctx():
        yield db_session

    monkeypatch.setattr(onboarding_emails, "get_db_context", _ctx)
    selection = await selection_of(db_session, kit, "asha")
    application = await ApplicationService(db_session).ensure(await db_session.get(OurInternship, selection.internship_id), selection)
    old = await give_link(db_session, kit, "asha")

    # 1. nothing assigned: the built-in invitation, exactly as before
    await onboarding_emails._send_invitation(application.id)
    assert len(mail.sent) == 1 and token_of(mail.sent[0]) and token_of(mail.sent[0]) != old
    assert where_is(await application_of(db_session, kit, "asha"), token_of(mail.sent[0])) == "active"

    # 2. the branded design assigned: same workflow, new look, newest link wins, the previous one stops working
    await built_in(client, auth_headers, "internship_onboarding_invite", INVITE_KEY, "Onboarding invitation", {"heading": "Welcome aboard, {{student_name}}"})
    await onboarding_emails._send_invitation(application.id)
    branded = mail.sent[1]
    assert "Welcome aboard, Asha Rao" in branded["html"] and "What you will do" in branded["html"] and branded["subject"].startswith("Complete your internship onboarding")
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, token_of(branded)) == "active" and where_is(app, token_of(mail.sent[0])) == "dead" and app.pending_token_hash is None
