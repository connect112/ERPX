"""
Announcements module — background tasks.

Email sending is dispatched through Celery, one task per recipient, so
posting an announcement (which can reach every user in the org) returns
immediately without blocking on SMTP for each address individually.
"""

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import run_async
from packages.email.service import email_service
from packages.email.templates import announcement_email

logger = get_logger(__name__)


@celery_app.task(name="announcements.send_announcement_email", bind=True, max_retries=3)
def send_announcement_email_task(
    self, to_email: str, full_name: str, title: str, body: str, scope_label: str
) -> None:
    subject, text, html = announcement_email(full_name, title, body, scope_label)
    success = run_async(email_service.send(to_email, subject, text, html))
    if not success:
        logger.warning("announcement_email_retry", to=to_email, attempt=self.request.retries)
        raise self.retry(countdown=30 * (self.request.retries + 1))
