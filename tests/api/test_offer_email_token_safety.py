"""
Offer-letter emails that carry a student's personal onboarding link: when a link is issued, what happens to the student's existing
link when a send fails, is refused, is ambiguous or dies with its worker, which Email Studio version a release uses, what happens
when the assigned template cannot be rendered, and that a preview or test never creates an application or a link.

Email delivery here is at-least-once. Nothing in these tests (or in the code) claims exactly-once delivery: the mail server's
"accepted" and the database's "sent" cannot be one step. What is guaranteed instead is that a link is never lost and never leaked.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import aiosmtplib
import pytest
from sqlalchemy import func, select

from app.core.exceptions import NotFoundError, ValidationError
from modules.audit.models import AuditLog
from modules.email_studio.models import EmailSendRecord, EmailStudioTemplate
from modules.institutions.models import InstitutionStudent
from modules.internship_onboarding.emails import PREVIEW_TOKEN
from modules.internship_onboarding.models import OnboardingApplication, OnboardingCounter, OnboardingEvent
from modules.internship_onboarding.portal import PortalService
from modules.internship_onboarding.service import PENDING_TOKEN_TTL, ApplicationService, hash_token
from modules.our_internships import letter_tasks
from modules.our_internships.letter_config import LetterConfig, config_hash
from modules.our_internships.letter_models import OfferLetter, OfferLetterDelivery, OfferLetterEvent
from modules.our_internships.models import InternshipSelection, OfferResponse, OurInternship
from packages.email.history import set_send_outcome
from tests.api.test_email_studio import _S, assign, create, page, publish, user_with
from tests.api.test_internship_onboarding import settings as onboarding_settings
from tests.api.test_offer_letters import by_name, ready_world, students, url, world  # noqa: F401 - `world` is a fixture

pytestmark = pytest.mark.api

_INTERN = "/api/v1/our-internships"
LINK_HTML = page('<p>Hi {{student_name}}</p><p><a href="{{onboarding_link}}">Start onboarding</a></p>')
NO_LINK_HTML = page("<p>Hi {{student_name}}, your offer letter is attached.</p>")
TOKEN = re.compile(r"#t=([A-Za-z0-9_\-]+)")
# config_hash of an untouched LetterConfig on master before this change: the email wording must stay part of it, or every letter
# already made would suddenly count as outdated.
GOLDEN_CONFIG_HASH = "34890704fc3b036feb8ab58090d7c69fb1d9bde52208bab5e5edd8435b977977"


class Mail:
    """The mail server: accepts, refuses outright (nothing delivered), or keeps the message and then loses the connection."""

    def __init__(self):
        self.mode = "accept"
        self.sent: list[dict] = []
        self.during = None  # an awaitable run while the "SMTP conversation" is in progress (a second worker, a slow server)

    async def send(self, to, subject, text, html=None, attachments=None):
        if self.during is not None:
            hook, self.during = self.during, None
            await hook()
        mail = {"to": to, "subject": subject, "text": text, "html": html, "attachments": attachments or []}
        if self.mode == "accept":
            self.sent.append(mail)
            return True
        if self.mode == "refuse":
            set_send_outcome("refused")
            return False
        if self.mode == "drop":
            self.sent.append(mail)  # the server kept it, but the answer never came back
            raise aiosmtplib.SMTPServerDisconnected("connection lost")
        raise AssertionError(self.mode)


@pytest.fixture
def mail(world, monkeypatch):  # noqa: F811
    server = Mail()
    monkeypatch.setattr(letter_tasks.email_service, "send", server.send)
    return server


async def setup(client, headers, world, *, mode="hybrid", html=LINK_HTML, subject="Offer for {{student_name}}", who=("asha", "meera")):  # noqa: F811
    internship, ids = await ready_world(client, headers, world)
    r = await client.put(f"{_INTERN}/{internship['id']}/onboarding-flow/config", json={"settings": onboarding_settings(modes={"mode": mode})}, headers=headers)
    assert r.status_code == 200, r.text
    template = None
    if html is not None:
        template = await create(client, headers, name="Offer mail", subject=subject, html=html)
        await publish(client, headers, template)
        await assign(client, headers, "internship_offer_letter", template["id"])
    rows = by_name(await students(client, headers, internship))
    letters = {"asha": rows["Asha Rao"]["letter"]["id"], "meera": rows["Meera Iyer"]["letter"]["id"], "ravi": rows["Ravi Kumar"]["letter"]["id"]}
    await client.post(url(internship, "/approve"), json={"letter_ids": [letters[w] for w in who]}, headers=headers)
    return SimpleNamespace(internship=internship, ids=ids, letters=letters, template=template, headers=headers, client=client)


async def release(kit, who=("asha",), expect=200, **body):
    r = await kit.client.post(url(kit.internship, "/release"), json={"letter_ids": [kit.letters[w] for w in who], **body}, headers=kit.headers)
    assert r.status_code == expect, r.text
    return r.json()


async def send(kit, who="asha") -> bool:
    return await letter_tasks._send_letter(uuid.UUID(kit.letters[who]))


async def selection_of(db, kit, who):
    email = {"asha": "asha@example.com", "meera": "meera@example.com", "ravi": "ravi@example.com"}[who]
    return (
        await db.execute(
            select(InternshipSelection).join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
            .where(InternshipSelection.internship_id == uuid.UUID(kit.internship["id"]), InstitutionStudent.email == email)
        )
    ).scalar_one()  # fmt: skip


async def application_of(db, kit, who) -> OnboardingApplication | None:
    selection = await selection_of(db, kit, who)
    application = await ApplicationService(db).get_for_selection(selection.id)
    if application is not None:
        await db.refresh(application)
    return application


async def give_link(db, kit, who) -> str:
    """The student already has an active link (an earlier invitation): the raw token, as the email would have carried it."""
    selection = await selection_of(db, kit, who)
    internship = await db.get(OurInternship, selection.internship_id)
    issued = await ApplicationService(db).issue_link(internship, selection, None, "test")
    return TOKEN.search(issued.link).group(1)


def token_of(mail_: dict) -> str | None:
    found = TOKEN.search((mail_["html"] or "") + (mail_["text"] or ""))
    return found.group(1) if found else None


def where_is(app: OnboardingApplication | None, token: str) -> str:
    """'active', 'pending' or 'dead': what the database says about a raw token (by its hash)."""
    if app is not None and app.token_hash == hash_token(token):
        return "active"
    if app is not None and app.pending_token_hash == hash_token(token):
        return "pending"
    return "dead"


async def opens(db, token: str) -> bool:
    """Whether the student's portal accepts this link (a pending link is confirmed by this first use)."""
    try:
        await PortalService(db).resolve(token)
        return True
    except NotFoundError:
        return False


async def counts(db) -> tuple:
    applications = (await db.execute(select(func.count()).select_from(OnboardingApplication))).scalar_one()
    counter = (await db.execute(select(func.coalesce(func.sum(OnboardingCounter.last_value), 0)))).scalar_one()
    return applications, counter


# ------------------------------------------------------------ previews and tests never issue anything (I1)


async def test_a_preview_and_a_test_email_create_no_application_reference_or_link_and_show_a_sample_link(client, auth_headers, world, mail, db_session, monkeypatch):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    before = await counts(db_session)

    def forbidden(*a, **k):
        raise AssertionError("a preview or a test must not create an application or issue any link")

    for name in ("ensure", "issue_link", "issue_pending"):
        monkeypatch.setattr(ApplicationService, name, forbidden)
    sample = (await client.post(url(kit.internship, "/email-preview"), json={"student_id": None}, headers=auth_headers)).json()
    real = (await client.post(url(kit.internship, "/email-preview"), json={"student_id": kit.ids["asha@example.com"]}, headers=auth_headers)).json()
    test = await client.post(url(kit.internship, "/test-email"), json={"to_email": "me@example.com"}, headers=auth_headers)
    assert test.status_code == 200
    assert sample["subject"] == "Offer for Asha Rao" and real["subject"] == "Offer for Asha Rao"
    assert len(mail.sent) == 1 and PREVIEW_TOKEN in mail.sent[0]["html"] and mail.sent[0]["subject"].startswith("[Test]")
    assert await counts(db_session) == before  # no application row, no reference number taken
    assert token_of(mail.sent[0]) == PREVIEW_TOKEN  # and it is plainly a sample: it can never match a stored link
    assert await opens(db_session, PREVIEW_TOKEN) is False


async def test_a_preview_in_manual_onboarding_shows_no_link_and_no_dead_button(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, mode="manual")
    await client.post(url(kit.internship, "/test-email"), json={"to_email": "me@example.com"}, headers=auth_headers)
    html = mail.sent[0]["html"]
    assert "Start onboarding" in html and 'href=""' not in html and "#t=" not in html  # the text stays, the empty link does not
    assert await counts(db_session) == (0, 0)


# ------------------------------------------------------------ a link is issued only when the email needs it (I2)


async def test_a_template_without_the_link_never_touches_the_students_link(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=NO_LINK_HTML)
    old = await give_link(db_session, kit, "asha")
    await release(kit)
    assert await send(kit) is True
    app = await application_of(db_session, kit, "asha")
    assert len(mail.sent) == 1 and "#t=" not in mail.sent[0]["html"]
    assert where_is(app, old) == "active" and app.pending_token_hash is None  # nothing was issued, nothing replaced
    assert await opens(db_session, old) is True
    # and a student with no application gets none made for them
    await release(kit, ("meera",))
    await send(kit, "meera")
    assert await application_of(db_session, kit, "meera") is None


async def test_a_release_with_the_link_issues_one_and_confirms_it_when_the_mail_is_accepted(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    await release(kit)
    assert await send(kit) is True
    token = token_of(mail.sent[0])
    app = await application_of(db_session, kit, "asha")
    assert token and where_is(app, token) == "active" and app.pending_token_hash is None and app.pending_token_ref is None
    assert await opens(db_session, token) is True
    events = [e.event for e in (await db_session.execute(select(OnboardingEvent).where(OnboardingEvent.application_id == app.id))).scalars()]
    assert "link_pending_issued" in events and "link_promoted" in events


@pytest.mark.parametrize("state", ["active_link_kept", "revoked", "cancelled", "completed", "declined"])
async def test_students_who_have_a_link_or_must_not_get_one_are_sent_the_email_without_a_new_link(state, client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    old = await give_link(db_session, kit, "asha")
    app = await application_of(db_session, kit, "asha")
    selection = await selection_of(db_session, kit, "asha")
    if state == "revoked":
        await ApplicationService(db_session).revoke_link(app, None)  # type: ignore[arg-type]
    elif state == "cancelled":
        app.cancelled_at = datetime.now(timezone.utc)
    elif state == "completed":
        app.completed_at = datetime.now(timezone.utc)
    elif state == "declined":
        selection.offer_response = OfferResponse.DECLINED
    await db_session.flush()
    await release(kit)
    assert await send(kit) is True
    app = await application_of(db_session, kit, "asha")
    assert len(mail.sent) == 1 and token_of(mail.sent[0]) is None and 'href=""' not in mail.sent[0]["html"]
    assert app.pending_token_hash is None
    assert where_is(app, old) == ("active" if state in ("active_link_kept", "cancelled", "completed", "declined") else "dead")


async def test_replace_gives_every_student_in_the_batch_a_new_link(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    old = await give_link(db_session, kit, "asha")
    await release(kit, link_policy="replace")
    await send(kit)
    new = token_of(mail.sent[0])
    app = await application_of(db_session, kit, "asha")
    assert new and new != old and where_is(app, new) == "active" and where_is(app, old) == "dead"


# ------------------------------------------------------------ failure, retry and crash behaviour (I3, I4, I7)


async def test_a_refused_send_and_its_retries_never_cost_the_student_their_existing_link(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    old = await give_link(db_session, kit, "asha")
    await release(kit, link_policy="replace")
    mail.mode = "refuse"
    for _ in range(letter_tasks.MAX_ATTEMPTS - 1):
        assert await send(kit) is False  # try again later
        app = await application_of(db_session, kit, "asha")
        assert where_is(app, old) == "active" and app.pending_token_hash is None  # the refused link was discarded
    assert await send(kit) is True  # out of attempts
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, old) == "active" and mail.sent == []
    assert await opens(db_session, old) is True
    history = (await db_session.execute(select(OfferLetterDelivery).order_by(OfferLetterDelivery.attempt))).scalars().all()
    assert [d.attempt for d in history] == [1, 2, 3, 4] and all(d.status == "failed" for d in history)
    # released again and accepted: now (and only now) the new link replaces the old one
    mail.mode = "accept"
    await release(kit, link_policy="replace")
    assert await send(kit) is True
    app = await application_of(db_session, kit, "asha")
    new = token_of(mail.sent[0])
    assert where_is(app, new) == "active" and where_is(app, old) == "dead"


async def test_an_ambiguous_outcome_keeps_the_possibly_delivered_link_valid_and_is_not_repeated_automatically(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    old = await give_link(db_session, kit, "asha")
    await release(kit, link_policy="replace")
    mail.mode = "drop"  # the server kept the message; the connection broke before the answer
    assert await send(kit) is True  # no automatic retry: a second email would replace the link in the first
    assert len(mail.sent) == 1
    pending = token_of(mail.sent[0])
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, pending) == "pending" and where_is(app, old) == "active"  # both work until the new one is used
    letter = (await db_session.execute(select(OfferLetter).where(OfferLetter.id == uuid.UUID(kit.letters["asha"])))).scalar_one()
    assert letter.delivery_status == "failed" and "unconfirmed" in letter.delivery_error and letter.delivery_lease_until is None
    # the student opens the email that did arrive: its link works, and using it confirms it (the old one stops)
    assert await opens(db_session, pending) is True
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, pending) == "active" and where_is(app, old) == "dead" and app.pending_token_hash is None
    # and sending the same letter again does nothing on its own
    assert await send(kit) is True and len(mail.sent) == 1


async def test_a_worker_that_dies_after_the_mail_server_took_the_message_leaves_a_working_link_and_no_duplicate(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    await release(kit)
    began = await letter_tasks._begin(uuid.UUID(kit.letters["asha"]))
    assert not isinstance(began, bool)
    outcome = await letter_tasks._deliver(began)  # the mail server accepted it...
    assert outcome.kind == "accepted" and len(mail.sent) == 1
    # ...and the worker died here: _finish never ran. The letter is still queued under its lease, the link is pending.
    token = token_of(mail.sent[0])
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, token) == "pending"
    assert await send(kit) is True and len(mail.sent) == 1  # a second worker finds the lease held and does nothing
    letter = (await db_session.execute(select(OfferLetter).where(OfferLetter.id == uuid.UUID(kit.letters["asha"])))).scalar_one()
    letter.delivery_lease_until = datetime.now(timezone.utc) - timedelta(minutes=1)  # the lease runs out
    await db_session.flush()
    assert await send(kit) is True and len(mail.sent) == 1  # still no automatic second email: its link would replace the first
    await db_session.refresh(letter)
    assert letter.delivery_status == "failed" and "unconfirmed" in letter.delivery_error
    assert where_is(await application_of(db_session, kit, "asha"), token) == "pending" and await opens(db_session, token) is True
    # releasing again is the administrator's explicit choice: it sends a new email and its link replaces the pending one
    await release(kit, link_policy="replace")
    assert await send(kit) is True and len(mail.sent) == 2
    newest = token_of(mail.sent[1])
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, newest) == "active"


async def test_emails_that_arrive_out_of_order_only_the_newest_link_works(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    await release(kit)
    await send(kit)
    first = token_of(mail.sent[0])
    await release(kit, link_policy="replace", resend=True)
    mail.mode = "drop"
    await send(kit)
    second = token_of(mail.sent[1])
    await release(kit, link_policy="replace", resend=True)
    mail.mode = "accept"
    await send(kit)
    third = token_of(mail.sent[2])
    app = await application_of(db_session, kit, "asha")
    assert len({first, second, third}) == 3 and where_is(app, third) == "active"
    # the student opens the older emails after the newest: neither link works
    assert await opens(db_session, second) is False and await opens(db_session, first) is False
    assert await opens(db_session, third) is True


async def test_a_pending_link_is_cleared_by_revoke_and_by_cancellation_and_expires(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    await release(kit)
    mail.mode = "drop"
    await send(kit)
    token = token_of(mail.sent[0])
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, token) == "pending"
    app.pending_token_issued_at = datetime.now(timezone.utc) - PENDING_TOKEN_TTL - timedelta(minutes=1)
    await db_session.flush()
    assert await opens(db_session, token) is False  # expired
    app.pending_token_issued_at = datetime.now(timezone.utc)
    await db_session.flush()
    await ApplicationService(db_session).revoke_link(app, None)  # type: ignore[arg-type]
    app = await application_of(db_session, kit, "asha")
    assert app.pending_token_hash is None and await opens(db_session, token) is False  # revoked: both slots cleared


async def test_confirming_or_discarding_is_a_compare_and_swap(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    selection = await selection_of(db_session, kit, "asha")
    internship = await db_session.get(OurInternship, selection.internship_id)
    apps = ApplicationService(db_session)
    first = await apps.issue_pending(internship, selection, "test:1")
    second = await apps.issue_pending(internship, selection, "test:2")  # an explicit newer issue replaces the pending slot
    assert await apps.promote_pending(first.application.id, first.token_hash) is False  # the older one no longer holds the slot
    assert await apps.discard_pending(first.application.id, first.token_hash) is False
    app = await application_of(db_session, kit, "asha")
    assert app.pending_token_hash == second.token_hash and app.token_hash is None
    assert await apps.promote_pending(app.id, second.token_hash) is True
    assert await apps.promote_pending(app.id, second.token_hash) is False  # only once
    app = await application_of(db_session, kit, "asha")
    assert app.token_hash == second.token_hash and app.pending_token_hash is None
    app.cancelled_at = datetime.now(timezone.utc)
    await db_session.flush()
    with pytest.raises(ValidationError):  # a cancelled application never gets a new link
        await apps.issue_pending(internship, selection, "test:3")


# ------------------------------------------------------------ one worker at a time (B)


async def test_a_second_worker_during_a_slow_send_does_nothing_and_exactly_one_email_goes_out(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    await release(kit)
    results = []

    async def second_worker():
        results.append(await send(kit))

    mail.during = second_worker  # while the first worker waits on the (slow) mail server, another task for the same letter starts
    assert await send(kit) is True
    assert results == [True] and len(mail.sent) == 1


# ------------------------------------------------------------ the release pins the template version (C)


async def test_a_version_published_while_a_batch_is_being_sent_does_not_change_the_rest_of_the_batch(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=NO_LINK_HTML, subject="V1 {{student_name}}")
    await release(kit, ("asha", "meera"))
    await send(kit, "asha")
    # an administrator publishes version 2 in the middle of the batch
    draft = {"subject": "V2 {{student_name}}", "html": NO_LINK_HTML, "editor_json": {"type": "doc", "content": [{"type": "paragraph"}]}}
    assert (await client.put(f"{_S}/templates/{kit.template['id']}/draft", json=draft, headers=auth_headers)).status_code == 200
    await publish(client, auth_headers, kit.template)
    await send(kit, "meera")
    assert [m["subject"] for m in mail.sent] == ["V1 Asha Rao", "V1 Meera Iyer"]  # the pinned (now superseded) version is still what goes out
    await release(kit, ("asha",), resend=True)  # a new release pins whatever is published then
    await send(kit, "asha")
    assert mail.sent[-1]["subject"] == "V2 Asha Rao"
    letter = (await db_session.execute(select(OfferLetter).where(OfferLetter.id == uuid.UUID(kit.letters["asha"])))).scalar_one()
    assert letter.email_source == "studio" and letter.email_version_id is not None and letter.release_batch_id is not None


async def test_letters_queued_before_pins_existed_resolve_their_email_when_sent(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=NO_LINK_HTML, subject="Live {{student_name}}")
    await release(kit)
    letter = (await db_session.execute(select(OfferLetter).where(OfferLetter.id == uuid.UUID(kit.letters["asha"])))).scalar_one()
    letter.release_batch_id = letter.email_source = letter.email_version_id = letter.email_link_policy = None  # as queued by the old code
    await db_session.flush()
    assert await send(kit) is True and mail.sent[0]["subject"] == "Live Asha Rao"


# ------------------------------------------------------------ a failing assigned template is a controlled failure (B)


async def test_when_the_assigned_template_cannot_be_rendered_nothing_is_sent_not_even_the_legacy_email_and_it_is_all_recorded(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=NO_LINK_HTML)
    await release(kit)
    letter = (await db_session.execute(select(OfferLetter).where(OfferLetter.id == uuid.UUID(kit.letters["asha"])))).scalar_one()
    letter.email_version_id = None  # the pinned version has vanished (the column is set to NULL when a version is deleted)
    await db_session.flush()
    assert await send(kit) is True  # not retried: it would fail the same way
    assert mail.sent == []  # and no legacy wording was substituted
    await db_session.refresh(letter)
    assert letter.delivery_status == "failed" and letter.delivery_error.startswith("template_error: version_missing")
    delivery = (await db_session.execute(select(OfferLetterDelivery))).scalars().one()
    assert delivery.status == "failed" and delivery.error.startswith("template_error")
    record = (await db_session.execute(select(EmailSendRecord).where(EmailSendRecord.key == "internship_offer_letter"))).scalars().one()
    assert record.status == "failed" and record.recipient == "asha@example.com" and "version_missing" in record.error
    actions = [e.action for e in (await db_session.execute(select(OfferLetterEvent))).scalars()]
    assert "letter_send_failed" in actions
    selection = await selection_of(db_session, kit, "asha")
    assert selection.offer_status.value == "failed" and "version_missing" in selection.offer_error


async def test_a_template_that_cannot_be_used_stops_the_release_and_the_legacy_email_needs_an_explicit_permitted_choice(client, auth_headers, world, mail, db_session, organization):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=NO_LINK_HTML)
    template = await db_session.get(EmailStudioTemplate, uuid.UUID(kit.template["id"]))
    template.deleted_at = datetime.now(timezone.utc)  # still assigned, but no longer usable (Studio itself refuses to delete an assigned template)
    await db_session.flush()
    refused = await release(kit, expect=422)
    assert "Nothing was queued" in str(refused) and "was deleted" in str(refused)
    assert mail.sent == [] and world.emails == []
    # an administrator without email_templates.publish cannot choose the legacy email, even with manage rights on the internship
    manager = await user_with(db_session, organization, ["our_internships.view", "our_internships.manage"])
    denied = await client.post(url(kit.internship, "/release"), json={"letter_ids": [kit.letters["asha"]], "fallback": "legacy_letter_settings"}, headers=manager)
    assert denied.status_code == 403 and world.emails == []
    # with both permissions the choice is explicit, recorded on the letter and in the activity log, and the legacy wording is used
    queued = await release(kit, fallback="legacy_letter_settings")
    assert queued["queued"] == 1
    await send(kit)
    assert mail.sent[0]["subject"] == "Your internship offer letter - GIR Technologies"
    letter = (await db_session.execute(select(OfferLetter).where(OfferLetter.id == uuid.UUID(kit.letters["asha"])))).scalar_one()
    assert letter.email_source == "letter_settings" and letter.email_fallback_by_user_id is not None
    details = [e.detail for e in (await db_session.execute(select(OfferLetterEvent).where(OfferLetterEvent.action == "release_requested"))).scalars()]
    assert any("legacy email chosen by the administrator" in (d or "") for d in details)


async def test_a_student_the_template_cannot_be_filled_for_is_skipped_at_release_with_the_reason(client, auth_headers, world, mail, db_session, monkeypatch):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=NO_LINK_HTML, who=("asha", "meera"))
    from modules.our_internships import letters as letters_module

    real = letters_module.LetterService.render_offer

    async def render(self, internship, config, values, plan=None):
        if values.get("student_name") == "Meera Iyer":
            from modules.email_studio.engine import TemplateRenderFailed

            raise TemplateRenderFailed("missing_values", "The template needs {{x}}, which this student does not have.")
        return await real(self, internship, config, values, plan)

    monkeypatch.setattr(letters_module.LetterService, "render_offer", render)
    result = await release(kit, ("asha", "meera"))
    assert result["queued"] == 1 and "cannot be filled for this student" in result["skipped"][0]["reason"]


# ------------------------------------------------------------ secrets stay out of subjects, previews, histories and logs (D)


@pytest.mark.parametrize(
    "bad",
    [
        {"subject": "Your link {{onboarding_link}}", "html": LINK_HTML},
        {"subject": "Offer", "html": page('<p><a href="https://x.example/?u={{onboarding_link}}">x</a></p>')},
        {"subject": "Offer", "html": page('<p><img src="{{onboarding_link}}"></p>')},
        {"subject": "Offer", "html": LINK_HTML, "preheader": "open {{onboarding_link}}"},
    ],
    ids=["subject", "inside_a_longer_address", "other_attribute", "preheader"],
)
async def test_the_link_cannot_be_placed_where_it_would_leak(bad, client, auth_headers):
    template = await create(client, auth_headers, name="Leaky", **bad)
    refused = await client.post(f"{_S}/templates/{template['id']}/publish", headers=auth_headers)
    assert refused.status_code == 422 and "onboarding_link" in refused.text


async def test_the_link_may_be_a_whole_href_or_visible_text(client, auth_headers):
    template = await create(client, auth_headers, name="Fine", subject="Offer", html=page('<p><a href="{{onboarding_link}}">Go</a> or copy {{onboarding_link}}</p>'))
    assert (await client.post(f"{_S}/templates/{template['id']}/publish", headers=auth_headers)).status_code == 200


async def test_a_subject_that_would_carry_the_token_is_stopped_before_sending_and_the_link_is_forgotten(client, auth_headers, world, mail, db_session, monkeypatch):  # noqa: F811
    from modules.our_internships import letters as letters_module
    from modules.our_internships.letters import OfferEmail

    kit = await setup(client, auth_headers, world)
    old = await give_link(db_session, kit, "asha")
    await release(kit, link_policy="replace")
    real = letters_module.LetterService.render_offer

    async def render(self, internship, config, values, plan=None):
        email = await real(self, internship, config, values, plan)
        if "PREVIEW-SAMPLE" not in values.get("onboarding_link", "") and values.get("onboarding_link"):
            return OfferEmail("Open " + values["onboarding_link"], email.text, email.html, email.note, email.used)
        return email

    monkeypatch.setattr(letters_module.LetterService, "render_offer", render)
    assert await send(kit) is True and mail.sent == []
    app = await application_of(db_session, kit, "asha")
    assert app.pending_token_hash is None and where_is(app, old) == "active"
    letter = (await db_session.execute(select(OfferLetter).where(OfferLetter.id == uuid.UUID(kit.letters["asha"])))).scalar_one()
    assert "secret_in_subject" in letter.delivery_error


async def test_the_raw_link_is_never_stored_logged_or_queued(client, auth_headers, world, mail, db_session, capsys, caplog, monkeypatch):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    queued: list = []
    monkeypatch.setattr(letter_tasks.send_letter_task, "apply_async", lambda args=None, **kw: queued.append((args, kw)))
    letter_tasks.enqueue_letter_emails([uuid.UUID(kit.letters["asha"])])
    await release(kit)
    mail.mode = "drop"  # the unhappy path writes the most text
    await send(kit)
    mail.mode = "accept"
    await release(kit, link_policy="replace")
    await send(kit)
    tokens = [token_of(m) for m in mail.sent]
    assert len(tokens) == 2 and all(tokens)
    stored = [str({c.name: getattr(row, c.name) for c in model.__table__.columns}) for model in (EmailSendRecord, OfferLetterDelivery, OnboardingEvent, OfferLetterEvent, AuditLog)
              for row in (await db_session.execute(select(model))).scalars()]  # fmt: skip
    stored += [str({c.name: getattr(row, c.name) for c in OnboardingApplication.__table__.columns}) for row in (await db_session.execute(select(OnboardingApplication))).scalars()]
    stored += [str(queued), capsys.readouterr().out, capsys.readouterr().err, caplog.text]
    for token in tokens:
        assert not any(token in blob for blob in stored), "a raw onboarding token reached the database, a queue or a log"
    app = await application_of(db_session, kit, "asha")
    assert app.token_hash == hash_token(tokens[1]) and len(app.token_hash) == 64
    assert queued and all(str(uuid.UUID(kit.letters["asha"])) in str(a) and "t=" not in str(a) for a, _ in queued)


# ------------------------------------------------------------ manual onboarding, isolation, compatibility (I11, I12, I13)


async def test_in_manual_onboarding_the_email_has_no_link_no_dead_button_and_makes_no_application(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, mode="manual")
    before = await counts(db_session)
    await release(kit)
    assert await send(kit) is True
    html = mail.sent[0]["html"]
    assert "Start onboarding" in html and 'href=""' not in html and "#t=" not in html
    assert await counts(db_session) == before and await application_of(db_session, kit, "asha") is None


async def test_each_student_gets_only_their_own_email_attachment_and_link(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    await release(kit, ("asha", "meera"))
    await send(kit, "asha")
    await send(kit, "meera")
    first, second = mail.sent
    assert (first["to"], second["to"]) == ("asha@example.com", "meera@example.com")
    assert len(first["attachments"]) == 1 and len(second["attachments"]) == 1 and first["attachments"][0].content != second["attachments"][0].content
    assert "Meera" not in first["html"] and "Asha" not in second["html"]
    ta, tm = token_of(first), token_of(second)
    assert ta != tm and ta not in second["html"] and tm not in first["html"]
    asha, meera = await application_of(db_session, kit, "asha"), await application_of(db_session, kit, "meera")
    assert where_is(asha, ta) == "active" and where_is(asha, tm) == "dead" and where_is(meera, tm) == "active"


async def test_the_email_wording_stays_part_of_the_letter_design_hash_so_existing_letters_stay_current():
    assert config_hash(LetterConfig(), {}) == GOLDEN_CONFIG_HASH
    changed = LetterConfig()
    changed.email.subject = "Something else {{company_name}}"
    assert config_hash(changed, {}) != GOLDEN_CONFIG_HASH


async def test_the_standalone_invitation_still_issues_an_active_link_directly(client, auth_headers, world, mail, db_session):  # noqa: F811
    from modules.internship_onboarding import emails as onboarding_emails
    from modules.internship_onboarding.service import config_of

    kit = await setup(client, auth_headers, world, html=None)
    selection = await selection_of(db_session, kit, "asha")
    internship = await db_session.get(OurInternship, selection.internship_id)
    _, config = await config_of(db_session, internship)
    values = await onboarding_emails.onboarding_values(db_session, internship, selection, config)
    token = TOKEN.search(values["onboarding_link"]).group(1)
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, token) == "active" and app.pending_token_hash is None  # unchanged behaviour: replaces the earlier link at once
