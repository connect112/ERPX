"""
Accounting / Invoices — background tasks.

Overdue detection runs on a schedule rather than being computed on every
read, so `Invoice.status` genuinely transitions to OVERDUE (visible in
filters, reports, and notifications) instead of being a display-only
computed flag. Wire into Celery beat, e.g.:

    celery_app.conf.beat_schedule["accounting-mark-overdue-invoices"] = {
        "task": "accounting.mark_overdue_invoices",
        "schedule": crontab(hour=0, minute=30),
    }
"""

import asyncio

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context
from modules.accounting.invoices.service import InvoiceService
from modules.organizations.repository import OrganizationRepository

logger = get_logger(__name__)


async def _mark_overdue_for_all_organizations() -> int:
    total_flipped = 0
    async with get_db_context() as db:
        org_repo = OrganizationRepository(db)
        organizations = await org_repo.list_all(skip=0, limit=10_000)
        service = InvoiceService(db)
        for org in organizations:
            if org.is_active:
                total_flipped += await service.refresh_overdue_statuses(org.id)
    return total_flipped


@celery_app.task(
    name="accounting.mark_overdue_invoices",
    # Idempotent (re-flipping an already-OVERDUE invoice is a no-op), so a
    # transient DB failure is safe to retry with exponential backoff rather
    # than waiting a full day for the next beat run. Mirrors the retry policy
    # on crm.followups.* — the other two scheduled tasks previously had none.
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def mark_overdue_invoices_task() -> None:
    count = asyncio.run(_mark_overdue_for_all_organizations())
    logger.info("overdue_invoices_marked", count=count)
