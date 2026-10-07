"""
Hackathons module -- background tasks.

One Celery task per participant so a couple of hundred welcome emails never
block the request that created the accounts, and one failing address
retries alone. Sends are staggered a couple of seconds apart so the SMTP
relay isn't hit with a single burst.
"""

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import run_async
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
