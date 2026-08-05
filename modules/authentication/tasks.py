"""
Authentication module — background tasks.

Email sending is dispatched through Celery so registration/login/reset
requests return immediately without blocking on SMTP. Register this
module with the Celery app's autodiscovery once more modules exist:

    celery_app.autodiscover_tasks(["modules.authentication", ...])
"""

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import run_async
from packages.email.service import email_service
from packages.email.templates import password_reset_email, verification_email

logger = get_logger(__name__)


@celery_app.task(name="authentication.send_verification_email", bind=True, max_retries=3)
def send_verification_email_task(self, to_email: str, full_name: str, verification_url: str) -> None:
    subject, text, html = verification_email(full_name, verification_url)
    success = run_async(email_service.send(to_email, subject, text, html))
    if not success:
        logger.warning("verification_email_retry", to=to_email, attempt=self.request.retries)
        raise self.retry(countdown=30 * (self.request.retries + 1))


@celery_app.task(name="authentication.send_password_reset_email", bind=True, max_retries=3)
def send_password_reset_email_task(self, to_email: str, full_name: str, reset_url: str) -> None:
    subject, text, html = password_reset_email(full_name, reset_url)
    success = run_async(email_service.send(to_email, subject, text, html))
    if not success:
        logger.warning("password_reset_email_retry", to=to_email, attempt=self.request.retries)
        raise self.retry(countdown=30 * (self.request.retries + 1))
