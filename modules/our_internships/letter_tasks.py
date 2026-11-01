"""
Offer letter generator -- background work: making the PDFs of a batch of students, and emailing one released letter.

Generating runs one student at a time, each in its own transaction, so progress shows on the dashboard as it goes and one
failed letter never stops the rest. Emailing is one task per letter so a bad address retries on its own; sends are staggered a
couple of seconds apart so a batch does not hit the mail relay as a single burst.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.institutions.models import Institution, InstitutionStudent
from modules.our_internships.letter_models import DeliveryStatus, LetterStatus, OfferLetter, OfferLetterDelivery
from modules.our_internships.letter_pdf import StudentFacts
from modules.our_internships.letters import LetterService, facts_of
from modules.our_internships.models import InternshipSelection, OfferStatus, OurInternship
from packages.email.history import set_send_meta
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


async def _onboarding_values(db, internship: OurInternship, selection: InternshipSelection | None) -> dict[str, str]:
    """The onboarding link and fee placeholders (a fresh link per email). A problem there never stops the letter."""
    from modules.internship_onboarding.emails import EMPTY, onboarding_values

    if selection is None:
        return dict(EMPTY)
    try:
        async with db.begin_nested():
            return await onboarding_values(db, internship, selection)
    except Exception:  # noqa: BLE001 - the letter is still sent, without a link
        logger.warning("offer_letter_onboarding_values_failed", selection_id=str(selection.id), exc_info=True)
        return dict(EMPTY)


async def _send_letter(letter_id: uuid.UUID) -> bool:
    """Email one released letter. True when there is nothing more to do (sent, or no longer wanted); False to try again."""
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
        letter.delivery_attempts += 1
        attempt = letter.delivery_attempts
        subject: str | None = None
        try:
            loaded = await service.load(internship)
            facts = StudentFacts(letter.student_name, letter.institution_name, "", recipient)
            if student is not None:
                institution = await db.get(Institution, student.institution_id)
                if institution is not None:
                    facts = facts_of(student, institution)
            values = service.email_values(loaded.config, facts, internship.title, letter.reference, letter.generated_at)
            values.update(await _onboarding_values(db, internship, selection))
            subject, text, html, note = await service.render_offer_email(internship, loaded.config, values)
            note.sent_by_user_id = letter.released_by_user_id
            set_send_meta(note)  # so the history shows the template and version that made this email
            sent = await email_service.send(
                recipient, subject, text, html,
                attachments=[EmailAttachment(filename=letter.filename or "OfferLetter.pdf", content=letter.pdf_data, mime_type="application/pdf")],
            )
            error = None if sent else "The email could not be delivered."
        except Exception as exc:  # noqa: BLE001 - a mail error must be recorded, not lost
            logger.warning("offer_letter_email_failed", letter_id=str(letter_id), exc_info=True)
            sent, error = False, f"{type(exc).__name__}: {str(exc)[:300]}"

        db.add(
            OfferLetterDelivery(
                organization_id=letter.organization_id, letter_id=letter.id, recipient_email=recipient, subject=(subject or "")[:255] or None,
                status="sent" if sent else "failed", attempt=attempt, error=None if sent else error,
            )
        )
        if sent:
            now = datetime.now(timezone.utc)
            letter.delivery_status = DeliveryStatus.SENT.value
            letter.status = LetterStatus.RELEASED.value
            letter.released_at = now
            letter.sent_to_email = recipient
            letter.delivery_error = None
            if selection is not None:
                selection.offer_status = OfferStatus.SENT
                selection.offer_sent_at = now
                selection.offer_error = None
            await service.log(internship, letter.released_by_user_id, "letter_sent", f"Emailed the letter to {recipient}", letter.id)
            await db.flush()
            return True
        letter.delivery_error = (error or "The email could not be delivered.")[:500]
        if selection is not None:
            selection.offer_error = letter.delivery_error[:255]
        if attempt >= MAX_ATTEMPTS:
            letter.delivery_status = DeliveryStatus.FAILED.value
            if selection is not None:
                selection.offer_status = OfferStatus.FAILED
            await service.log(internship, letter.released_by_user_id, "letter_send_failed", f"Could not email {recipient}: {letter.delivery_error}", letter.id)
            await db.flush()
            return True  # out of attempts: the admin sees the reason and can release again
        await db.flush()
        return False


@celery_app.task(name="our_internships.send_offer_letter", bind=True, max_retries=MAX_ATTEMPTS)
def send_letter_task(self, letter_id: str) -> None:
    if not run_async(_send_letter(uuid.UUID(letter_id))):
        logger.warning("offer_letter_email_retry", letter_id=letter_id, attempt=self.request.retries)
        raise self.retry(countdown=120 * (self.request.retries + 1))
