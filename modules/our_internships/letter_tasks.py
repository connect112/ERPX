"""
Offer letter generator -- background work: making the PDFs of a batch of students, and emailing one released letter.

Generating runs one student at a time, each in its own transaction, so progress shows on the dashboard as it goes and one
failed letter never stops the rest. Emailing is one task per letter so a bad address retries on its own; sends are staggered a
couple of seconds apart so a batch does not hit the mail relay as a single burst.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import undefer

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.institutions.models import Institution, InstitutionStudent
from modules.our_internships.letter_models import DeliveryStatus, LetterStatus, OfferLetter, OfferLetterDelivery
from modules.our_internships.letter_pdf import StudentFacts
from modules.our_internships.letters import LEASE_MINUTES, LetterService, OfferEmailPlan, facts_of
from modules.our_internships.models import InternshipSelection, OfferStatus, OurInternship
from packages.email.history import SendMeta, record_failure, redact, set_send_meta, take_send_outcome
from packages.email.service import EmailAttachment, email_service

logger = get_logger(__name__)

_STAGGER_SECONDS = 2
MAX_ATTEMPTS = 4


# ------------------------------------------------------------------ generating


def enqueue_generation(letter_ids: list[uuid.UUID]) -> None:
    generate_letters_task.apply_async(args=[[str(i) for i in letter_ids]])


async def generate_batch(letter_ids: list[uuid.UUID]) -> None:
    async with get_db_context() as db:
        await LetterService(db).mark_generating(letter_ids)
    for letter_id in letter_ids:
        try:
            async with get_db_context() as db:
                await LetterService(db).generate_one(letter_id)
        except Exception:  # noqa: BLE001 - the letter keeps its pending state; the admin can generate again
            logger.warning("offer_letter_generation_failed", letter_id=str(letter_id), exc_info=True)


@celery_app.task(name="our_internships.generate_offer_letters")
def generate_letters_task(letter_ids: list[str]) -> None:
    run_async(generate_batch([uuid.UUID(i) for i in letter_ids]))


# ------------------------------------------------------------------ emailing


def enqueue_letter_emails(letter_ids: list[uuid.UUID]) -> None:
    for position, letter_id in enumerate(letter_ids):
        send_letter_task.apply_async(args=[str(letter_id)], countdown=position * _STAGGER_SECONDS)


@dataclass
class _Outcome:
    kind: str  # "accepted" | "refused" (definitely not delivered) | "unknown" (it may have been delivered)
    error: str | None = None


@dataclass
class _Attempt:
    """One send attempt, between the database work before it and after it. ``token`` is a raw onboarding link: it exists only here
    in memory, and is never stored, logged, put on the task queue or shown in a repr."""

    letter_id: uuid.UUID
    batch_id: uuid.UUID | None
    number: int
    recipient: str
    filename: str
    subject: str
    note: Any
    pdf: bytes = field(repr=False, default=b"")
    text: str = field(repr=False, default="")
    html: str | None = field(repr=False, default=None)
    application_id: uuid.UUID | None = None
    token_hash: str | None = None
    token: str | None = field(repr=False, default=None)
    preset: _Outcome | None = None  # the attempt could not even start; finish it as failed without sending


LEASE = timedelta(minutes=LEASE_MINUTES)
_LINK_PLACEHOLDER = "onboarding_link"
# A letter that is queued but whose task never started (the message was lost with a worker) is queued again after this long. A
# duplicate task is harmless: whichever starts second finds the letter sent, or its lease held, and does nothing.
STUCK_AFTER = timedelta(minutes=60)
UNCONFIRMED_TEXT = (
    "the worker stopped while the email was being handed to the mail server, so it may have been delivered. It was not sent again on its "
    "own; if it carried an onboarding link, that link still works for 72 hours. Release the letter again only if the student did not get it."
)


def _ref_of(letter: OfferLetter) -> str:
    """Names the delivery a pending onboarding link belongs to (not secret; short enough for the column)."""
    batch = letter.release_batch_id.hex if letter.release_batch_id else "none"
    return f"ol:{letter.id.hex}:{batch}"


async def _plan_of(service: LetterService, letter: OfferLetter, internship: OurInternship) -> OfferEmailPlan:
    """The wording this letter's email uses: the one its release pinned, or (letters queued before releases pinned anything) the one
    assigned now."""
    if letter.email_source == "studio":
        return OfferEmailPlan("studio", letter.email_version_id)  # no version left = TemplateRenderFailed when it is rendered
    if letter.email_source == "letter_settings":
        return OfferEmailPlan("letter_settings", recovery_by=letter.email_fallback_by_user_id)
    return await service.plan_offer_email(internship.organization_id)


def _secrets_of(pending: Any) -> list[str]:
    """The raw link of a pending onboarding link and its bare token: whatever must never reach a stored or logged text."""
    if pending is None:
        return []
    return [pending.link, pending.link.split("#t=", 1)[-1]]


async def _fail_unsendable(
    db, service: LetterService, internship, letter: OfferLetter, selection, recipient: str, number: int, plan: OfferEmailPlan | None, code: str, message: str,
    secrets: list[str] | None = None,
) -> None:  # fmt: skip
    """A controlled, auditable failure: nothing is retried and no other wording is substituted. The reason is on the letter, in the
    delivery history, in the send history and in the activity log; any link in the text is removed before it is stored."""
    error = redact(f"{code}: {message}", secrets or [])[:500]
    db.add(OfferLetterDelivery(organization_id=letter.organization_id, letter_id=letter.id, recipient_email=recipient, subject=None, status="failed", attempt=number, error=error))
    letter.delivery_status = DeliveryStatus.FAILED.value
    letter.delivery_error = error
    letter.delivery_lease_until = None
    letter.delivery_handoff_at = None
    if selection is not None:
        selection.offer_status = OfferStatus.FAILED
        selection.offer_error = error[:255]
    note = SendMeta(
        organization_id=letter.organization_id, key="internship_offer_letter", module="Internships",
        template_id=plan.template_id if plan else None, version_id=plan.version_id if plan else None,
        source=(plan.source if plan else None), sent_by_user_id=letter.released_by_user_id,
    )  # fmt: skip
    record_failure(db, note, recipient, "", error)
    await service.log(internship, letter.released_by_user_id, "letter_send_failed", f"Not sent to {recipient}: {error}", letter.id)
    await db.flush()


async def _recover_expired(db, service: LetterService, apps: Any, internship, letter: OfferLetter, selection, recipient: str) -> str:
    """The letter is locked, still queued, and its lease ran out: a worker began an attempt and never reported how it ended.

    * "unconfirmed": the mail server may have been contacted (``delivery_handoff_at`` was recorded before that). The message may have
      been delivered, so the letter is marked failed with an "unconfirmed" reason and is NOT sent again on its own. Its pending link,
      if any, is left alone: if the email arrived, the link in it works.
    * "not_sent": the attempt never got as far as the mail server. Nothing was delivered, so the pending link it made is forgotten
      and the caller may send again.
    * "gave_up": as not_sent, but the letter has already used all its attempts."""
    handed_off = letter.delivery_handoff_at is not None
    letter.delivery_lease_until = None
    letter.delivery_handoff_at = None
    if handed_off:
        await _fail_unsendable(db, service, internship, letter, selection, recipient, letter.delivery_attempts, None, "unconfirmed", UNCONFIRMED_TEXT)
        return "unconfirmed"
    application = await apps.get_for_selection(selection.id) if selection is not None else None
    if application is not None:
        await apps.discard_pending_for(application.id, _ref_of(letter))
    if letter.delivery_attempts >= MAX_ATTEMPTS:
        await _fail_unsendable(db, service, internship, letter, selection, recipient, letter.delivery_attempts, None, "not_sent", "the worker stopped before the email reached the mail server, on every attempt. Nothing was delivered; release the letter again.")
        return "gave_up"
    error = "not_sent: the worker stopped before the email reached the mail server. Nothing was delivered; it is being sent again."
    db.add(OfferLetterDelivery(organization_id=letter.organization_id, letter_id=letter.id, recipient_email=recipient, subject=None, status="failed", attempt=letter.delivery_attempts, error=error))
    logger.warning("offer_letter_lease_expired_not_sent", letter_id=str(letter.id))
    return "not_sent"


async def _begin(letter_id: uuid.UUID) -> _Attempt | bool:
    """Everything before the mail server is contacted, in one short transaction. True: nothing (more) to do. Otherwise the attempt.

    If the wording uses the student's onboarding link and the release's link policy allows a new one, the link is issued here as a
    PENDING link and committed before anything is sent: the student's active link is untouched, and if the process dies after the
    mail server took the message the link in it still works (it is confirmed when the message is accepted, or on first use)."""
    from modules.email_studio.engine import AssignedTemplateUnusable, TemplateRenderFailed
    from modules.internship_onboarding.emails import link_values, preview_onboarding_values
    from modules.internship_onboarding.service import ApplicationService, config_of

    async with get_db_context() as db:
        letter = (
            await db.execute(select(OfferLetter).options(undefer(OfferLetter.pdf_data)).where(OfferLetter.id == letter_id).with_for_update())
        ).scalar_one_or_none()
        if letter is None or letter.delivery_status != DeliveryStatus.QUEUED.value or not letter.pdf_data:
            return True  # taken back, or already sent
        internship = (await db.execute(select(OurInternship).where(OurInternship.id == letter.internship_id))).scalar_one()
        selection = await db.get(InternshipSelection, letter.selection_id) if letter.selection_id else None
        student = await db.get(InstitutionStudent, letter.student_id) if letter.student_id else None
        recipient = (student.email if student and student.email else letter.student_email).strip()
        service = LetterService(db)
        apps = ApplicationService(db)
        moment = datetime.now(timezone.utc)

        if letter.delivery_lease_until is not None:
            if letter.delivery_lease_until > moment:
                return True  # another worker is sending this letter right now
            # The lease ran out: an earlier attempt started and never reported. If the mail server may have been contacted the
            # email may have been delivered, so it is not repeated automatically; otherwise nothing was sent and this attempt goes on.
            if await _recover_expired(db, service, apps, internship, letter, selection, recipient) != "not_sent":
                return True

        letter.delivery_attempts += 1
        number = letter.delivery_attempts
        letter.delivery_lease_until = moment + LEASE
        letter.delivery_handoff_at = None
        plan: OfferEmailPlan | None = None
        pending = None
        try:
            plan = await _plan_of(service, letter, internship)
            _, onboarding = await config_of(db, internship)
            loaded = await service.load(internship)
            facts = StudentFacts(letter.student_name, letter.institution_name, "", recipient)
            if student is not None:
                institution = await db.get(Institution, student.institution_id)
                if institution is not None:
                    facts = facts_of(student, institution)
            values = service.email_values(loaded.config, facts, internship.title, letter.reference, letter.generated_at)
            # a dry run with sample onboarding values: does the wording work, and does it use the link at all?
            dry = await service.render_offer(internship, loaded.config, {**values, **await preview_onboarding_values(db, internship, selection, onboarding)}, plan)
            if plan.source == "studio" and _LINK_PLACEHOLDER in dry.used and selection is not None:
                allowed, _ = await apps.link_eligibility(selection, onboarding, letter.email_link_policy or "keep_existing")
                if allowed:
                    pending = await apps.issue_pending(internship, selection, _ref_of(letter), onboarding)
            application = pending.application if pending else (await apps.get_for_selection(selection.id) if selection is not None else None)
            values.update(await link_values(db, onboarding, application, pending.link if pending else ""))
            try:
                email = await service.render_offer(internship, loaded.config, values, plan)
                if pending is not None and pending.link.split("#t=", 1)[-1] in email.subject:
                    raise TemplateRenderFailed("secret_in_subject", "The subject would contain the student's personal link.")
            except Exception:
                if pending is not None:
                    await apps.discard_pending(pending.application.id, pending.token_hash)  # nothing was sent: forget the link
                raise
        except (TemplateRenderFailed, AssignedTemplateUnusable) as exc:
            code, message = (exc.code, exc.message) if isinstance(exc, TemplateRenderFailed) else ("assignment_unusable", str(exc))
            await _fail_unsendable(db, service, internship, letter, selection, recipient, number, plan, "template_error: " + code, message, _secrets_of(pending))
            return True
        except Exception as exc:  # noqa: BLE001 - not a template problem (for example the database): recorded, and tried again like any failed send
            logger.warning("offer_letter_prepare_failed", letter_id=str(letter_id), error=type(exc).__name__)
            await db.flush()
            problem = redact(f"{type(exc).__name__}: {str(exc)[:300]}", _secrets_of(pending))
            return _Attempt(letter.id, letter.release_batch_id, number, recipient, letter.filename or "OfferLetter.pdf", "", None, preset=_Outcome("refused", problem))
        email.note.sent_by_user_id = letter.released_by_user_id
        await db.flush()
        return _Attempt(
            letter.id, letter.release_batch_id, number, recipient, letter.filename or "OfferLetter.pdf", email.subject, email.note,
            pdf=letter.pdf_data, text=email.text, html=email.html,
            application_id=pending.application.id if pending else None, token_hash=pending.token_hash if pending else None,
            token=pending.link if pending else None,
        )  # fmt: skip


async def _handoff(attempt: _Attempt) -> bool:
    """Record, and commit, that the mail server is about to be contacted; only the worker that still holds the lease may do so.

    This is what tells a worker that died BEFORE sending (nothing was delivered) from one that died DURING or AFTER (the message may
    have been). It is also a fence: if the lease already ran out and something else took the letter over, this attempt does not send."""
    from modules.internship_onboarding.service import ApplicationService

    async with get_db_context() as db:
        moment = datetime.now(timezone.utc)
        taken = await db.execute(
            update(OfferLetter)
            .where(
                OfferLetter.id == attempt.letter_id, OfferLetter.delivery_status == DeliveryStatus.QUEUED.value, OfferLetter.delivery_attempts == attempt.number,
                OfferLetter.release_batch_id.is_not_distinct_from(attempt.batch_id), OfferLetter.delivery_handoff_at.is_(None), OfferLetter.delivery_lease_until > moment,
            )
            .values(delivery_handoff_at=moment, delivery_lease_until=moment + LEASE)
            .execution_options(synchronize_session=False)
        )  # fmt: skip
        if taken.rowcount == 1:
            return True
        if attempt.token_hash is not None and attempt.application_id is not None:
            await ApplicationService(db).discard_pending(attempt.application_id, attempt.token_hash)  # nothing was sent: forget its link
        logger.warning("offer_letter_lease_lost_before_sending", letter_id=str(attempt.letter_id))
        return False


async def _deliver(attempt: _Attempt) -> _Outcome:
    """The one place the mail server is contacted: no database transaction is held open here."""
    from packages.email.service import is_refusal

    if attempt.preset is not None:
        return attempt.preset
    set_send_meta(attempt.note)  # so the history shows the template and version that made this email
    try:
        sent = await email_service.send(
            attempt.recipient, attempt.subject, attempt.text, attempt.html,
            attachments=[EmailAttachment(filename=attempt.filename, content=attempt.pdf, mime_type="application/pdf")],
        )
    except Exception as exc:  # noqa: BLE001 - a mail error must be recorded, not lost
        logger.warning("offer_letter_email_failed", letter_id=str(attempt.letter_id), error=type(exc).__name__)
        return _Outcome("refused" if is_refusal(exc) else "unknown", redact(f"{type(exc).__name__}: {str(exc)[:300]}", [attempt.token or ""]))
    signal = take_send_outcome()
    if sent:
        return _Outcome("accepted")
    return _Outcome("unknown" if signal == "unknown" else "refused", "The email could not be delivered.")


async def _finish(attempt: _Attempt, outcome: _Outcome) -> bool:
    """Record how the attempt ended. True when there is nothing more to do; False to try again later.

    A message the mail server accepted confirms the pending link (the old one stops working then, compare-and-swap). A message that
    was definitely refused discards it. A message whose outcome is unknown keeps it: the email may carry it, so it is neither
    discarded nor repeated automatically."""
    from modules.internship_onboarding.service import ApplicationService

    async with get_db_context() as db:
        letter = (await db.execute(select(OfferLetter).where(OfferLetter.id == attempt.letter_id).with_for_update())).scalar_one_or_none()
        if letter is None:
            return True
        internship = (await db.execute(select(OurInternship).where(OurInternship.id == letter.internship_id))).scalar_one()
        selection = await db.get(InternshipSelection, letter.selection_id) if letter.selection_id else None
        service = LetterService(db)
        apps = ApplicationService(db)
        # still this release's latest attempt? (a newer release, or another worker, may have moved on while the mail was being sent)
        current = letter.release_batch_id == attempt.batch_id and letter.delivery_attempts == attempt.number
        carries_link = attempt.token_hash is not None and attempt.application_id is not None
        unconfirmed = outcome.kind == "unknown"  # the mail server may have taken it: never sent again on its own
        error = None
        if outcome.kind != "accepted":
            note = "unconfirmed: the mail server may have received it, so it was not sent again. " + ("Its link works for 72 hours. " if carries_link else "")
            error = ((note if unconfirmed else "") + (outcome.error or "The email could not be delivered."))[:500]
        db.add(
            OfferLetterDelivery(
                organization_id=letter.organization_id, letter_id=letter.id, recipient_email=attempt.recipient, subject=(attempt.subject or "")[:255] or None,
                status="sent" if outcome.kind == "accepted" else "failed", attempt=attempt.number, error=error,
            )
        )
        if outcome.kind == "accepted":
            if carries_link:
                await apps.promote_pending(attempt.application_id, attempt.token_hash, reason="sent")
            if not current:
                await db.flush()
                return True
            moment = datetime.now(timezone.utc)
            letter.delivery_status = DeliveryStatus.SENT.value
            letter.status = LetterStatus.RELEASED.value
            letter.released_at = moment
            letter.sent_to_email = attempt.recipient
            letter.delivery_error = None
            letter.delivery_lease_until = None
            letter.delivery_handoff_at = None
            if selection is not None:
                selection.offer_status = OfferStatus.SENT
                selection.offer_sent_at = moment
                selection.offer_error = None
            await service.log(internship, letter.released_by_user_id, "letter_sent", f"Emailed the letter to {attempt.recipient}", letter.id)
            await db.flush()
            return True
        if carries_link and outcome.kind == "refused":
            await apps.discard_pending(attempt.application_id, attempt.token_hash)
        if not current:
            await db.flush()
            return True
        letter.delivery_lease_until = None
        letter.delivery_handoff_at = None
        letter.delivery_error = (error or "The email could not be delivered.")[:500]
        if selection is not None:
            selection.offer_error = letter.delivery_error[:255]
        if unconfirmed or attempt.number >= MAX_ATTEMPTS:
            letter.delivery_status = DeliveryStatus.FAILED.value
            if selection is not None:
                selection.offer_status = OfferStatus.FAILED
            await service.log(internship, letter.released_by_user_id, "letter_send_failed", f"Could not email {attempt.recipient}: {letter.delivery_error}", letter.id)
            await db.flush()
            return True  # out of attempts, or not repeated because the link may already be out: the admin sees why and can release again
        await db.flush()
        return False


async def _send_letter(letter_id: uuid.UUID) -> bool:
    """Email one released letter. True when there is nothing more to do (sent, failed for good, or no longer wanted); False to try
    again. Email delivery is at-least-once: nothing here can make "the mail server took it" and "the database says so" one step."""
    began = await _begin(letter_id)
    if began is True:
        return True
    if began.preset is None and not await _handoff(began):  # type: ignore[union-attr]
        return True  # the lease was lost before anything was sent
    return await _finish(began, await _deliver(began))  # type: ignore[arg-type]


async def recover_deliveries(batch: int = 200) -> dict[str, int]:
    """Find letters a dead worker left "sending" and settle them, so none stays that way for good.

    * lease ran out, mail server never contacted: nothing was delivered, so the letter is sent again (counted ``resent``);
    * lease ran out after the mail server may have been contacted: marked failed with an "unconfirmed" reason, never sent again on its
      own (``unconfirmed``); a worker that is merely slow and finishes later still settles the letter correctly;
    * queued with no lease for a long time: its task was lost before it started, so it is queued again (``requeued``).

    Email delivery stays at-least-once; this never makes it exactly-once."""
    found = {"unconfirmed": 0, "resent": 0, "gave_up": 0, "requeued": 0}
    moment = datetime.now(timezone.utc)
    queued = DeliveryStatus.QUEUED.value
    async with get_db_context() as db:
        expired = (await db.execute(select(OfferLetter.id).where(OfferLetter.delivery_status == queued, OfferLetter.delivery_lease_until < moment).limit(batch))).scalars().all()
        idle = (
            await db.execute(
                select(OfferLetter.id).where(OfferLetter.delivery_status == queued, OfferLetter.delivery_lease_until.is_(None), OfferLetter.updated_at < moment - STUCK_AFTER).limit(batch)
            )
        ).scalars().all()  # fmt: skip
    again: list[uuid.UUID] = []
    from modules.internship_onboarding.service import ApplicationService

    for letter_id in expired:
        async with get_db_context() as db:
            letter = (await db.execute(select(OfferLetter).where(OfferLetter.id == letter_id).with_for_update(skip_locked=True))).scalar_one_or_none()
            if letter is None or letter.delivery_status != queued or letter.delivery_lease_until is None or letter.delivery_lease_until >= datetime.now(timezone.utc):
                continue  # settled meanwhile, or another worker is on it
            internship = (await db.execute(select(OurInternship).where(OurInternship.id == letter.internship_id))).scalar_one()
            selection = await db.get(InternshipSelection, letter.selection_id) if letter.selection_id else None
            student = await db.get(InstitutionStudent, letter.student_id) if letter.student_id else None
            recipient = (student.email if student and student.email else letter.student_email).strip()
            verdict = await _recover_expired(db, LetterService(db), ApplicationService(db), internship, letter, selection, recipient)
        if verdict == "not_sent":
            again.append(letter_id)
            found["resent"] += 1
        else:
            found[verdict] += 1
    if idle:
        async with get_db_context() as db:
            await db.execute(update(OfferLetter).where(OfferLetter.id.in_(idle)).values(updated_at=moment))  # so it is not queued again every run
        again += [i for i in idle if i not in again]
        found["requeued"] = len(idle)
    if again:
        enqueue_letter_emails(again)
    return found


@celery_app.task(name="our_internships.recover_offer_letter_deliveries")
def recover_deliveries_task() -> dict[str, int]:
    result = run_async(recover_deliveries())
    if any(result.values()):
        logger.info("offer_letter_delivery_recovery", **result)
    return result


@celery_app.task(name="our_internships.send_offer_letter", bind=True, max_retries=MAX_ATTEMPTS)
def send_letter_task(self, letter_id: str) -> None:
    if not run_async(_send_letter(uuid.UUID(letter_id))):
        logger.warning("offer_letter_email_retry", letter_id=letter_id, attempt=self.request.retries)
        raise self.retry(countdown=120 * (self.request.retries + 1))
