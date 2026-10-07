"""
Hackathons module -- background tasks.

One Celery task per participant so a couple of hundred welcome emails never
block the request that created the accounts, and one failing address
retries alone. Sends are staggered a couple of seconds apart so the SMTP
relay isn't hit with a single burst.
"""

import uuid

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.hackathons.ai_evaluation import AIEvaluationService, EvaluationError
from modules.hackathons.models import Hackathon
from modules.email_templates.render import render_email_sync
from packages.email.service import email_service

logger = get_logger(__name__)

_STAGGER_SECONDS = 2


@celery_app.task(name="hackathons.send_participant_welcome", bind=True, max_retries=5)
def send_participant_welcome_task(
    self,
    to_email: str,
    full_name: str,
    hackathon_title: str,
    set_password_url: str,
    login_url: str,
    hackathon_id: str | None = None,
    organization_id: str | None = None,
) -> None:
    # The hackathon's own wording if the organiser wrote one, else the organisation's, else the default.
    subject, text, html = render_email_sync(
        "hackathon_participant_welcome",
        {
            "full_name": full_name,
            "hackathon_title": hackathon_title,
            "set_password_url": set_password_url,
            "login_url": login_url,
        },
        organization_id=organization_id,
        hackathon_id=hackathon_id,
        recipient_email=to_email,
    )
    if not run_async(email_service.send(to_email, subject, text, html)):
        logger.warning("hackathon_welcome_email_retry", to=to_email, attempt=self.request.retries)
        raise self.retry(countdown=60 * (self.request.retries + 1))


async def _ai_evaluate(hackathon_id: uuid.UUID, submission_id: uuid.UUID, automatic: bool) -> str | None:
    """Evaluate one submission; returns a retry reason when the AI service was merely unavailable."""
    async with get_db_context() as db:
        hackathon = (await db.execute(select(Hackathon).where(Hackathon.id == hackathon_id))).scalar_one_or_none()
        if hackathon is None:
            return None
        try:
            await AIEvaluationService(db).evaluate(hackathon, submission_id, automatic=automatic)
        except EvaluationError as exc:
            # The reason is saved on the submission for staff to see.
            logger.info("hackathon_ai_evaluation_skipped", submission_id=str(submission_id), reason=str(exc)[:160])
            return str(exc) if exc.retryable else None
    return None


@celery_app.task(name="hackathons.ai_evaluate_submission", bind=True, max_retries=2, ignore_result=True)
def ai_evaluate_submission_task(self, hackathon_id: str, submission_id: str, automatic: bool = True) -> None:
    reason = run_async(_ai_evaluate(uuid.UUID(hackathon_id), uuid.UUID(submission_id), automatic))
    if reason:
        raise self.retry(countdown=60 * (self.request.retries + 1))


def enqueue_ai_evaluations(
    hackathon_id: uuid.UUID, submission_ids: list[uuid.UUID], *, automatic: bool, countdown: int = 0
) -> bool:
    """Queue evaluations a few seconds apart; never raises (a missed one can be started with the button)."""
    try:
        for position, submission_id in enumerate(submission_ids):
            ai_evaluate_submission_task.apply_async(
                args=[str(hackathon_id), str(submission_id), automatic],
                countdown=countdown + position * 3,
                retry=False,
            )
    except Exception:  # noqa: BLE001 - broker trouble
        logger.warning("hackathon_ai_enqueue_failed", hackathon_id=str(hackathon_id), exc_info=True)
        return False
    return True


def enqueue_welcome_emails(
    logins: list[tuple[str, str, str]],
    hackathon_title: str,
    student_portal_url: str,
    hackathon_id: str | None = None,
    organization_id: str | None = None,
) -> None:
    """logins: (email, full_name, reset_token) for each newly created account."""
    base = student_portal_url.rstrip("/")
    for position, (email, full_name, token) in enumerate(logins):
        try:
            send_participant_welcome_task.apply_async(
                args=[
                    email,
                    full_name,
                    hackathon_title,
                    f"{base}/reset-password?token={token}",
                    f"{base}/login",
                    hackathon_id,
                    organization_id,
                ],
                countdown=position * _STAGGER_SECONDS,
                retry=False,
            )
        except Exception:  # noqa: BLE001 - the accounts are already saved; "Forgot password" still works
            logger.warning("hackathon_welcome_enqueue_failed", to=email, exc_info=True)
