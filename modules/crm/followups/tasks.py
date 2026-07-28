"""
CRM Follow-ups module — background tasks.

WhatsApp/SMS sending is dispatched through Celery, the same way
`modules.authentication.tasks` dispatches verification/reset emails, so
scheduling a follow-up returns immediately without blocking on an
external provider's API.
"""

import asyncio

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from packages.sms.client import sms_service
from packages.whatsapp.client import whatsapp_service

logger = get_logger(__name__)


@celery_app.task(name="crm.followups.send_whatsapp_reminder", bind=True, max_retries=3)
def send_followup_whatsapp_task(self, to_phone: str, lead_name: str, scheduled_at_iso: str) -> None:
    message = (
        f"Hi {lead_name}, this is a reminder from GIR Technologies about your scheduled "
        f"follow-up on {scheduled_at_iso}. Reply to this message if you'd like to reschedule."
    )
    success = asyncio.run(whatsapp_service.send_text(to_phone, message))
    if not success:
        logger.warning("followup_whatsapp_retry", to=to_phone, attempt=self.request.retries)
        raise self.retry(countdown=30 * (self.request.retries + 1))


@celery_app.task(name="crm.followups.send_sms_reminder", bind=True, max_retries=3)
def send_followup_sms_task(self, to_phone: str, lead_name: str, scheduled_at_iso: str) -> None:
    message = (
        f"Hi {lead_name}, GIR Technologies has a follow-up scheduled with you on "
        f"{scheduled_at_iso}. Call us if you need to reschedule."
    )
    success = asyncio.run(sms_service.send(to_phone, message))
    if not success:
        logger.warning("followup_sms_retry", to=to_phone, attempt=self.request.retries)
        raise self.retry(countdown=30 * (self.request.retries + 1))
