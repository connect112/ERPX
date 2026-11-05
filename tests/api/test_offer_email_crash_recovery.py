"""
Offer-letter emails when a worker dies, a lease runs out, a task runs twice or the mail server's answer is lost.

What these tests pin down (and what they do NOT claim): delivery is at-least-once. A letter is never left "sending" for good, but an
email whose hand-over to the mail server may have happened is never repeated on its own: it is marked "unconfirmed" for an
administrator to decide. Nothing here promises exactly-once delivery.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from modules.audit.models import AuditLog
from modules.email_studio.engine import TemplateRenderFailed
from modules.email_studio.models import EmailSendRecord
from modules.internship_onboarding.emails import PREVIEW_TOKEN
from modules.our_internships import letter_tasks
from modules.our_internships.letter_models import OfferLetter, OfferLetterDelivery, OfferLetterEvent
from modules.our_internships.letters import LetterService
from tests.api.test_offer_email_token_safety import (  # noqa: F401 - fixtures and helpers shared with the other Phase 1 tests
    NO_LINK_HTML,
    application_of,
    give_link,
    mail,
    opens,
    release,
    send,
    setup,
    token_of,
    where_is,
)
from tests.api.test_offer_letters import world  # noqa: F401 - a fixture

pytestmark = pytest.mark.api


async def letter_of(db, kit, who="asha") -> OfferLetter:
    letter = (await db.execute(select(OfferLetter).where(OfferLetter.id == uuid.UUID(kit.letters[who])))).scalar_one()
    await db.refresh(letter)
    return letter


async def expire_lease(db, kit, who="asha") -> None:
    letter = await letter_of(db, kit, who)
    letter.delivery_lease_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db.flush()


@pytest.fixture
def queue(monkeypatch):
    """Records what the recovery sweep puts on the task queue, instead of using a broker."""
    queued: list[uuid.UUID] = []
    monkeypatch.setattr(letter_tasks, "enqueue_letter_emails", lambda ids: queued.extend(ids))
    return queued


async def die_before_the_mail_server(kit):
    """A worker that started the attempt (link issued as pending, lease taken) and died before contacting the mail server."""
    began = await letter_tasks._begin(uuid.UUID(kit.letters["asha"]))
    assert not isinstance(began, bool)
    return began


async def die_after_the_mail_server(kit):
    """A worker that handed the message to the mail server and died before it could record the answer."""
    began = await die_before_the_mail_server(kit)
    assert await letter_tasks._handoff(began)
    outcome = await letter_tasks._deliver(began)
    return began, outcome


# ------------------------------------------------------------ worker death: nothing delivered


async def test_a_worker_that_died_before_the_mail_server_is_recovered_and_the_email_goes_out_once(client, auth_headers, world, mail, queue, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    old = await give_link(db_session, kit, "asha")
    await release(kit, link_policy="replace")
    await die_before_the_mail_server(kit)
    app = await application_of(db_session, kit, "asha")
    assert app.pending_token_hash is not None and mail.sent == []

    assert await letter_tasks.recover_deliveries() == {"unconfirmed": 0, "resent": 0, "gave_up": 0, "requeued": 0}  # the lease is still alive
    assert (await letter_of(db_session, kit)).delivery_lease_until is not None

    await expire_lease(db_session, kit)
    assert await letter_tasks.recover_deliveries() == {"unconfirmed": 0, "resent": 1, "gave_up": 0, "requeued": 0}
    letter = await letter_of(db_session, kit)
    assert queue == [letter.id] and mail.sent == []  # recovery only queues the letter; it never sends
    assert letter.delivery_status == "queued" and letter.delivery_lease_until is None and letter.delivery_handoff_at is None
    app = await application_of(db_session, kit, "asha")
    assert app.pending_token_hash is None and where_is(app, old) == "active"  # the unsent link is forgotten, the student's link untouched
    history = (await db_session.execute(select(OfferLetterDelivery).where(OfferLetterDelivery.letter_id == letter.id))).scalars().all()
    assert [h.status for h in history] == ["failed"] and history[0].error.startswith("not_sent:")

    assert await send(kit) is True  # the queued task runs
    assert len(mail.sent) == 1
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, token_of(mail.sent[0])) == "active" and where_is(app, old) == "dead"
    assert (await letter_of(db_session, kit)).delivery_status == "sent"
    assert await send(kit) is True and len(mail.sent) == 1  # a duplicate task finds it sent
    assert await letter_tasks.recover_deliveries() == {"unconfirmed": 0, "resent": 0, "gave_up": 0, "requeued": 0}


async def test_a_letter_that_used_all_its_attempts_without_ever_reaching_the_mail_server_is_failed_not_looped(client, auth_headers, world, mail, queue, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    await release(kit)
    await die_before_the_mail_server(kit)
    letter = await letter_of(db_session, kit)
    letter.delivery_attempts = letter_tasks.MAX_ATTEMPTS
    await db_session.flush()
    await expire_lease(db_session, kit)
    assert (await letter_tasks.recover_deliveries())["gave_up"] == 1
    letter = await letter_of(db_session, kit)
    assert queue == [] and letter.delivery_status == "failed" and letter.delivery_error.startswith("not_sent:") and mail.sent == []


# ------------------------------------------------------------ worker death: possibly delivered


async def test_a_worker_that_died_after_the_mail_server_is_marked_unconfirmed_and_never_sent_again(client, auth_headers, world, mail, queue, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    old = await give_link(db_session, kit, "asha")
    await release(kit, link_policy="replace")
    began, outcome = await die_after_the_mail_server(kit)
    assert outcome.kind == "accepted" and len(mail.sent) == 1
    sent_token = token_of(mail.sent[0])
    letter = await letter_of(db_session, kit)
    assert letter.delivery_handoff_at is not None and letter.delivery_status == "queued"

    await expire_lease(db_session, kit)
    assert await letter_tasks.recover_deliveries() == {"unconfirmed": 1, "resent": 0, "gave_up": 0, "requeued": 0}
    letter = await letter_of(db_session, kit)
    assert queue == [] and len(mail.sent) == 1  # nothing was sent or queued again
    assert letter.delivery_status == "failed" and letter.delivery_error.startswith("unconfirmed:") and "may have been delivered" in letter.delivery_error
    assert letter.delivery_lease_until is None and letter.delivery_handoff_at is None
    # visible where administrators already look: the letter row, the delivery history, the send history and the activity log
    assert (await db_session.execute(select(OfferLetterDelivery.error).where(OfferLetterDelivery.letter_id == letter.id))).scalars().all()[-1].startswith("unconfirmed:")
    assert any((r.error or "").startswith("unconfirmed:") for r in (await db_session.execute(select(EmailSendRecord).where(EmailSendRecord.key == "internship_offer_letter"))).scalars())
    events = (await db_session.execute(select(OfferLetterEvent))).scalars().all()
    assert any("unconfirmed" in str(e.__dict__) for e in events)
    # the link in the email that may have arrived still works; the student's old link keeps working until it is used
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, sent_token) == "pending" and where_is(app, old) == "active"
    assert await opens(db_session, sent_token) is True
    # and neither the sweep nor a duplicate task sends it again
    assert await letter_tasks.recover_deliveries() == {"unconfirmed": 0, "resent": 0, "gave_up": 0, "requeued": 0}
    assert await send(kit) is True and len(mail.sent) == 1


async def test_the_same_holds_for_an_email_with_no_link(client, auth_headers, world, mail, queue, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=NO_LINK_HTML)
    await release(kit)
    await die_after_the_mail_server(kit)
    await expire_lease(db_session, kit)
    assert (await letter_tasks.recover_deliveries())["unconfirmed"] == 1
    assert (await letter_of(db_session, kit)).delivery_error.startswith("unconfirmed:") and queue == [] and len(mail.sent) == 1


async def test_a_slow_worker_that_finishes_after_the_sweep_settles_the_letter_correctly(client, auth_headers, world, mail, queue, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    old = await give_link(db_session, kit, "asha")
    await release(kit, link_policy="replace")
    began, outcome = await die_after_the_mail_server(kit)
    await expire_lease(db_session, kit)
    await letter_tasks.recover_deliveries()
    assert (await letter_of(db_session, kit)).delivery_status == "failed"  # the sweep could not know the worker was only slow
    assert await letter_tasks._finish(began, outcome) is True  # ...and it now reports that the mail server accepted the message
    letter = await letter_of(db_session, kit)
    assert letter.delivery_status == "sent" and letter.delivery_error is None and letter.delivery_lease_until is None
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, token_of(mail.sent[0])) == "active" and where_is(app, old) == "dead" and len(mail.sent) == 1


async def test_a_late_refusal_after_the_sweep_discards_the_link_and_replaces_the_unconfirmed_note(client, auth_headers, world, mail, queue, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    old = await give_link(db_session, kit, "asha")
    await release(kit, link_policy="replace")
    began = await die_before_the_mail_server(kit)
    assert await letter_tasks._handoff(began)
    await expire_lease(db_session, kit)
    await letter_tasks.recover_deliveries()
    await letter_tasks._finish(began, letter_tasks._Outcome("refused", "550 mailbox unavailable"))  # the late answer: definitely not delivered
    letter = await letter_of(db_session, kit)
    assert letter.delivery_status == "failed" and "550" in letter.delivery_error and "unconfirmed" not in letter.delivery_error
    app = await application_of(db_session, kit, "asha")
    assert app.pending_token_hash is None and where_is(app, old) == "active"


# ------------------------------------------------------------ duplicate task execution and fencing


async def test_a_second_task_for_a_letter_whose_first_attempt_is_still_in_progress_does_nothing(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    await release(kit)
    began = await die_before_the_mail_server(kit)  # the first task is mid-way
    assert await letter_tasks._begin(uuid.UUID(kit.letters["asha"])) is True  # the lease is held
    assert await send(kit) is True and mail.sent == []
    assert await letter_tasks._handoff(began) and await letter_tasks._finish(began, await letter_tasks._deliver(began)) is True
    assert len(mail.sent) == 1 and await send(kit) is True and len(mail.sent) == 1


async def test_a_stale_worker_whose_lease_was_taken_over_does_not_send(client, auth_headers, world, mail, queue, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    old = await give_link(db_session, kit, "asha")
    await release(kit, link_policy="replace")
    stale = await die_before_the_mail_server(kit)  # a worker that was merely paused
    await expire_lease(db_session, kit)
    await letter_tasks.recover_deliveries()  # the sweep decides nothing was sent and queues the letter again
    assert await send(kit) is True and len(mail.sent) == 1  # a fresh worker sends it
    sent_token = token_of(mail.sent[0])
    assert await letter_tasks._handoff(stale) is False  # the paused worker wakes up: it no longer holds the letter, so it must not send
    assert len(mail.sent) == 1
    app = await application_of(db_session, kit, "asha")
    assert where_is(app, sent_token) == "active" and where_is(app, old) == "dead"  # its own (long forgotten) link did not disturb that


# ------------------------------------------------------------ uncertain mail-server answers


async def test_an_uncertain_answer_is_never_retried_whether_or_not_the_email_has_a_link(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=NO_LINK_HTML)
    await release(kit)
    mail.mode = "drop"
    assert await send(kit) is True  # True = nothing more to do: no automatic retry
    letter = await letter_of(db_session, kit)
    assert len(mail.sent) == 1 and letter.delivery_status == "failed" and letter.delivery_error.startswith("unconfirmed:")
    assert await send(kit) is True and len(mail.sent) == 1


async def test_a_definite_refusal_is_still_retried_and_gives_up_after_the_attempt_limit(client, auth_headers, world, mail, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, html=NO_LINK_HTML)
    await release(kit)
    mail.mode = "refuse"
    for attempt in range(1, letter_tasks.MAX_ATTEMPTS):
        assert await send(kit) is False  # try again later
        letter = await letter_of(db_session, kit)
        assert letter.delivery_status == "queued" and letter.delivery_attempts == attempt and letter.delivery_lease_until is None
    assert await send(kit) is True
    letter = await letter_of(db_session, kit)
    assert letter.delivery_status == "failed" and letter.delivery_attempts == letter_tasks.MAX_ATTEMPTS and mail.sent == []


# ------------------------------------------------------------ a task that was lost before it started


async def test_a_letter_whose_task_was_lost_is_queued_again_once_and_not_every_run(client, auth_headers, world, mail, queue, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world, who=("asha", "meera"))
    await release(kit, who=("asha", "meera"))
    assert (await letter_tasks.recover_deliveries())["requeued"] == 0  # just released: its task may simply be waiting in the queue
    asha = uuid.UUID(kit.letters["asha"])
    long_ago = datetime.now(timezone.utc) - letter_tasks.STUCK_AFTER - timedelta(minutes=1)
    await db_session.execute(update(OfferLetter).where(OfferLetter.id == asha).values(updated_at=long_ago))
    assert (await letter_tasks.recover_deliveries())["requeued"] == 1
    assert queue == [asha]
    assert (await letter_tasks.recover_deliveries())["requeued"] == 0  # it was touched: not queued again until another hour passes
    assert await send(kit) is True and len(mail.sent) == 1 and await send(kit) is True and len(mail.sent) == 1  # a duplicate is harmless


# ------------------------------------------------------------ what is stored when a template fails


async def test_a_render_error_that_contains_the_link_is_redacted_everywhere_it_is_stored(client, auth_headers, world, mail, monkeypatch, db_session):  # noqa: F811
    kit = await setup(client, auth_headers, world)
    await release(kit, link_policy="replace")
    seen: dict[str, str] = {}
    real = LetterService.render_offer

    async def leaky(self, internship, config, values, plan=None):
        link = values.get("onboarding_link", "")
        if link and PREVIEW_TOKEN not in link:  # the real render, after the link was issued
            seen["link"] = link
            raise TemplateRenderFailed("render_error", f"could not draw the button for {link} (token {link.split('#t=')[-1]}) in the email")
        return await real(self, internship, config, values, plan)

    monkeypatch.setattr(LetterService, "render_offer", leaky)
    assert await send(kit) is True and mail.sent == []
    token = seen["link"].split("#t=")[-1]
    letter = await letter_of(db_session, kit)
    assert letter.delivery_status == "failed" and letter.delivery_error.startswith("template_error: render_error") and "[removed]" in letter.delivery_error
    stored = []
    for model in (OfferLetter, OfferLetterDelivery, OfferLetterEvent, EmailSendRecord, AuditLog):
        for row in (await db_session.execute(select(model))).scalars():
            stored.append(str({c.name: getattr(row, c.name, None) for c in row.__table__.columns if c.name != "pdf_data"}))
    assert not any(token in blob for blob in stored), "the onboarding link reached a stored error text"
    app = await application_of(db_session, kit, "asha")
    assert app.pending_token_hash is None  # and the unsent link was forgotten
