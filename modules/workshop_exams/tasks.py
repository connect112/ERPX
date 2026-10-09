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
from modules.workshop_exams.certificate_render import certificate_email, render_certificate, verify_url
from modules.workshop_exams.models import WorkshopExam, WorkshopExamAttendee
from modules.workshop_exams.service import WorkshopExamService
from modules.email_templates.render import render_email
from packages.email.service import EmailAttachment, email_service

logger = get_logger(__name__)

_STAGGER_SECONDS = 2


def exam_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/workshop-exam/{token}"


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
        subject, text, html = await render_email(
            db,
            "workshop_exam_invite",
            {
                "full_name": attendee.name,
                "exam_title": exam.title,
                "exam_url": exam_url(attendee.access_token),
                "duration_minutes": exam.duration_minutes,
            },
            organization_id=exam.organization_id,
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
        pdf = await render_certificate(db, exam, attendee)
        subject, text, html = await certificate_email(db, exam, attendee.name, (attendee.info or {}).get("team"))
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
            except ConflictError as exc:
                # Someone is still writing or a certificate is awaiting review; the next 5-minute
                # run tries again once they have finished.
                logger.info("workshop_certificates_waiting", exam_id=str(exam.id), reason=str(exc)[:120])
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
