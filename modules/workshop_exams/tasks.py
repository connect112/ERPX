"""
Workshop Exams module -- background tasks.

One Celery task per recipient (invite or certificate) so 200 emails never
block a request, and one failed address retries on its own without
re-sending to the others. Sends are staggered a couple of seconds apart
so a few hundred certificates don't hit the SMTP relay as a single burst.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.exceptions import ConflictError
from app.core.config import settings
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.organizations.models import Organization
from modules.workshop_exams.certificate_pdf import build_certificate_pdf
from modules.workshop_exams.certificate_template import build_templated_certificate_pdf
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee
from modules.workshop_exams.service import WorkshopExamService
from packages.email.service import EmailAttachment, email_service
from packages.email.templates import workshop_certificate_email, workshop_exam_invite_email

logger = get_logger(__name__)

_STAGGER_SECONDS = 2


def exam_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/workshop-exam/{token}"


def verify_url(certificate_number: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/verify-workshop-certificate/{certificate_number}"


def enqueue_invites(attendee_ids: list[uuid.UUID]) -> None:
    for position, attendee_id in enumerate(attendee_ids):
        send_invite_task.apply_async(args=[str(attendee_id)], countdown=position * _STAGGER_SECONDS)


def enqueue_invite_best_effort(attendee_id: uuid.UUID) -> None:
    """Queue a single backup invite without ever blocking or failing the caller.

    Used by self-registration, where the student already holds their exam link
    on screen: if the broker is down the email is lost, but the registration
    must not hang on kombu's connection retries or return a 500.
    """
    try:
        send_invite_task.apply_async(args=[str(attendee_id)], retry=False)
    except Exception:  # noqa: BLE001 - broker outage must not break registration
        logger.warning("workshop_exam_invite_enqueue_failed", attendee_id=str(attendee_id), exc_info=True)


def enqueue_certificates(attendee_ids: list[uuid.UUID]) -> None:
    for position, attendee_id in enumerate(attendee_ids):
        send_certificate_task.apply_async(args=[str(attendee_id)], countdown=position * _STAGGER_SECONDS)


async def _load(attendee_id: uuid.UUID, db) -> tuple[WorkshopExamAttendee, WorkshopExam] | None:
    attendee = (
        await db.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.id == attendee_id))
    ).scalar_one_or_none()
    if not attendee:
        return None
    exam = (await db.execute(select(WorkshopExam).where(WorkshopExam.id == attendee.exam_id))).scalar_one()
    return attendee, exam


async def _send_invite(attendee_id: uuid.UUID) -> bool:
    async with get_db_context() as db:
        loaded = await _load(attendee_id, db)
        if not loaded:
            return True
        attendee, exam = loaded
        subject, text, html = workshop_exam_invite_email(
            attendee.name, exam.title, exam_url(attendee.access_token), exam.duration_minutes
        )
        return await email_service.send(attendee.email, subject, text, html)


async def _send_certificate(attendee_id: uuid.UUID) -> bool:
    async with get_db_context() as db:
        loaded = await _load(attendee_id, db)
        if not loaded:
            return True
        attendee, exam = loaded
        if attendee.certificate_number is None or attendee.certificate_sent_at is not None:
            return True
        org = (
            await db.execute(select(Organization).where(Organization.id == exam.organization_id))
        ).scalar_one_or_none()
        issuer = org.name if org else "GIR Technologies"
        template = await WorkshopExamService(db).get_template(exam.id) if exam.has_certificate_template else None
        if template is not None:
            # The admin's own artwork with this attendee's name printed on it.
            pdf = build_templated_certificate_pdf(
                template_jpeg=template.data,
                width_px=template.width_px,
                height_px=template.height_px,
                layout=WorkshopExamService.layout_of(exam),
                attendee_name=attendee.name,
                certificate_number=attendee.certificate_number,
                verify_url=verify_url(attendee.certificate_number),
            )
        else:
            body = exam.certificate_text or f'has participated in the workshop "{exam.title}".'
            pdf = build_certificate_pdf(
                attendee_name=attendee.name,
                heading=exam.certificate_heading,
                body_text=body,
                issuer_name=issuer,
                issued_on=attendee.submitted_at or datetime.now(timezone.utc),
                certificate_number=attendee.certificate_number,
                verify_url=verify_url(attendee.certificate_number),
            )
        subject, text, html = workshop_certificate_email(attendee.name, exam.title)
        safe_name = "".join(ch if ch.isalnum() else "_" for ch in attendee.name).strip("_") or "participant"
        sent = await email_service.send(
            attendee.email,
            subject,
            text,
            html,
            attachments=[
                EmailAttachment(
                    filename=f"Certificate_{safe_name}.pdf", content=pdf, mime_type="application/pdf"
                )
            ],
        )
        if sent:
            attendee.certificate_sent_at = datetime.now(timezone.utc)
            await db.flush()
        return sent


@celery_app.task(name="workshop_exams.send_invite", bind=True, max_retries=3)
def send_invite_task(self, attendee_id: str) -> None:
    if not run_async(_send_invite(uuid.UUID(attendee_id))):
        raise self.retry(countdown=60 * (self.request.retries + 1))


@celery_app.task(name="workshop_exams.send_certificate", bind=True, max_retries=5)
def send_certificate_task(self, attendee_id: str) -> None:
    if not run_async(_send_certificate(uuid.UUID(attendee_id))):
        logger.warning("workshop_certificate_retry", attendee_id=attendee_id, attempt=self.request.retries)
        raise self.retry(countdown=120 * (self.request.retries + 1))


async def _dispatch_due() -> int:
    queued = 0
    async with get_db_context() as db:
        service = WorkshopExamService(db)
        for exam in await service.due_exams():
            try:
                ids = await service.dispatch_certificates(exam)
            except ConflictError:
                # Someone is still inside their time limit; the next 5-minute
                # run tries again once they have finished.
                logger.info("workshop_certificates_waiting_for_writers", exam_id=str(exam.id))
                continue
            queued += len(ids)
            logger.info("workshop_certificates_dispatched", exam_id=str(exam.id), count=len(ids))
            # Persist the certificate numbers before queueing the sends
            # that read them back.
            await db.commit()
            try:
                enqueue_certificates(ids)
            except Exception:  # noqa: BLE001 - broker trouble: don't mark the exam as done
                # Numbers are kept; clearing the flag lets the next tick queue
                # whoever still has no certificate instead of losing them.
                logger.warning("workshop_certificates_enqueue_failed", exam_id=str(exam.id), exc_info=True)
                exam.certificates_dispatched_at = None
                await db.commit()
                queued -= len(ids)
    return queued


@celery_app.task(name="workshop_exams.dispatch_due_certificates")
def dispatch_due_certificates_task() -> int:
    return run_async(_dispatch_due())
