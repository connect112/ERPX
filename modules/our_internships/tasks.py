"""
Our Internships -- background task that emails one student's offer letter.

One Celery task per student so a few hundred offers never block a request and one failing address retries on its own
without re-sending to the others. Sends are staggered a couple of seconds apart so a batch does not hit the SMTP relay as a
single burst. The status on each selected student (queued / sent / failed, with the last error) is what the admin sees.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import undefer

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.institutions.models import Institution, InstitutionStudent
from modules.our_internships.models import InternshipSelection, OfferStatus, OurInternship
from modules.our_internships.offer_letter import attachment_name, build_offer_pdf, render_offer_email
from modules.our_internships.offers import OfferService
from packages.email.service import EmailAttachment, email_service

logger = get_logger(__name__)

_STAGGER_SECONDS = 2
MAX_ATTEMPTS = 4


def enqueue_offers(selection_ids: list[uuid.UUID]) -> None:
    for position, selection_id in enumerate(selection_ids):
        send_offer_task.apply_async(args=[str(selection_id)], countdown=position * _STAGGER_SECONDS)


async def _send_offer(selection_id: uuid.UUID) -> bool:
    """Send one offer. True when there is nothing more to do (sent, or no longer wanted); False to try again later."""
    async with get_db_context() as db:
        row = (
            await db.execute(
                select(InternshipSelection, InstitutionStudent, Institution)
                .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
                .join(Institution, Institution.id == InstitutionStudent.institution_id)
                .where(InternshipSelection.id == selection_id)
            )
        ).first()
        if row is None:
            return True  # removed from the list while queued
        selection, student, institution = row
        if selection.offer_status != OfferStatus.QUEUED:
            return True  # already sent, or the admin took it back
        internship = (
            await db.execute(
                select(OurInternship)
                .options(undefer(OurInternship.offer_template_data))
                .where(OurInternship.id == selection.internship_id)
            )
        ).scalar_one()
        layout = OfferService.layout_of(internship)
        if not internship.offer_template_data or layout is None:
            selection.offer_status = OfferStatus.FAILED
            selection.offer_error = "The offer letter template is missing."
            await db.flush()
            return True

        selection.offer_attempts += 1
        try:
            values = OfferService(db).values_for(internship, student.name, institution.name, selection.offer_reference or "")
            pdf = build_offer_pdf(internship.offer_template_data, layout, values)
            subject, text, html = render_offer_email(
                internship.offer_email_subject,
                internship.offer_email_body,
                {
                    "full_name": student.name,
                    "internship_title": internship.title,
                    "institution": institution.name,
                    "reference": selection.offer_reference or "",
                },
            )
            sent = await email_service.send(
                student.email,
                subject,
                text,
                html,
                attachments=[EmailAttachment(filename=attachment_name(student.name), content=pdf, mime_type="application/pdf")],
            )
            error = None if sent else "The email could not be delivered."
        except Exception as exc:  # noqa: BLE001 - a bad PDF or a mail error must be recorded, not lost
            logger.warning("internship_offer_failed", selection_id=str(selection_id), exc_info=True)
            sent, error = False, f"{type(exc).__name__}: {str(exc)[:180]}"

        if sent:
            selection.offer_status = OfferStatus.SENT
            selection.offer_sent_at = datetime.now(timezone.utc)
            selection.offer_error = None
            await db.flush()
            return True
        selection.offer_error = (error or "The email could not be delivered.")[:255]
        if selection.offer_attempts >= MAX_ATTEMPTS:
            selection.offer_status = OfferStatus.FAILED
            await db.flush()
            return True  # out of attempts: the admin sees "Failed" with the reason and can send again
        await db.flush()
        return False


@celery_app.task(name="our_internships.send_offer", bind=True, max_retries=MAX_ATTEMPTS)
def send_offer_task(self, selection_id: str) -> None:
    if not run_async(_send_offer(uuid.UUID(selection_id))):
        logger.warning("internship_offer_retry", selection_id=selection_id, attempt=self.request.retries)
        raise self.retry(countdown=120 * (self.request.retries + 1))

