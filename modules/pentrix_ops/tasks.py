"""
Pentrix operations: scheduled tasks.

* pentrix.sync_bookings, pentrix.sync_candidates and pentrix.sync_payments (every minute): pull what Pentrix changed.
* pentrix.reconcile_payments (00:10 and 06:10 India time): check the days that have closed against Pentrix.
* pentrix.dispatch_marketing (every minute): send the next batch of confirmed marketing email, at a limited rate. Pentrix also tells ERPX straight away when something changes; this
  pull is what guarantees nothing is missed if that message never arrived.
* pentrix.send_booking_reminders (every minute): send the reminder emails that are due (see reminders.py).
"""
from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.pentrix_ops.candidates import PentrixCandidateService
from modules.pentrix_ops.client import PentrixClient
from modules.pentrix_ops.marketing import PentrixMarketingService
from modules.pentrix_ops.payments import PentrixPaymentService
from modules.pentrix_ops.reminders import send_due_reminders
from modules.pentrix_ops.service import PentrixBookingService, pentrix_organization_id

logger = get_logger(__name__)


async def _sync() -> int:
    if not PentrixClient.configured():
        return 0
    async with get_db_context() as db:
        return await PentrixBookingService(db).sync()


async def _sync_candidates() -> int:
    if not PentrixClient.configured():
        return 0
    async with get_db_context() as db:
        return await PentrixCandidateService(db).sync()


async def _sync_payments() -> int:
    if not PentrixClient.configured():
        return 0
    async with get_db_context() as db:
        return await PentrixPaymentService(db).sync()


async def _reconcile() -> dict:
    if not PentrixClient.configured():
        return {"days": 0, "mismatched": 0, "errors": 0}
    async with get_db_context() as db:
        rows = await PentrixPaymentService(db).reconcile_due(await pentrix_organization_id(db))
    return {"days": len(rows), "mismatched": sum(1 for r in rows if r.status == "mismatch"), "errors": sum(1 for r in rows if r.status == "error")}


async def _dispatch_marketing() -> dict:
    """Send the next batch of waiting marketing messages. The batch is claimed and committed first, and each message is then sent and
    recorded on its own, so a crash part-way leaves no message sent but unrecorded."""
    from app.core.config import settings

    async with get_db_context() as db:
        service = PentrixMarketingService(db)
        await service.retry_unsynced()
        ids = await service.claim(settings.PENTRIX_MARKETING_PER_MINUTE)
    done = {"sent": 0, "failed": 0, "skipped": 0, "queued": 0}
    for recipient_id in ids:
        async with get_db_context() as db:
            outcome = await PentrixMarketingService(db).process(recipient_id)
        done[outcome] = done.get(outcome, 0) + 1
    async with get_db_context() as db:
        await PentrixMarketingService(db).finish()
    return done


async def _remind() -> dict:
    async with get_db_context() as db:
        summary = await send_due_reminders(db)
    return {"sent": summary.sent, "failed": summary.failed, "skipped": summary.skipped}


@celery_app.task(name="pentrix.sync_bookings")
def sync_bookings_task() -> int:
    try:
        return run_async(_sync())
    except Exception:  # noqa: BLE001 - the next minute tries again from the saved cursor
        logger.warning("pentrix_sync_task_failed", exc_info=True)
        return -1


@celery_app.task(name="pentrix.sync_candidates")
def sync_candidates_task() -> int:
    try:
        return run_async(_sync_candidates())
    except Exception:  # noqa: BLE001 - the next minute tries again from the saved cursor
        logger.warning("pentrix_candidate_sync_task_failed", exc_info=True)
        return -1


@celery_app.task(name="pentrix.sync_payments")
def sync_payments_task() -> int:
    try:
        return run_async(_sync_payments())
    except Exception:  # noqa: BLE001 - the next minute tries again from the saved cursor
        logger.warning("pentrix_payment_sync_task_failed", exc_info=True)
        return -1


@celery_app.task(name="pentrix.reconcile_payments")
def reconcile_payments_task() -> dict:
    """After each day closes in India: check the closed days against Pentrix, repair what differs, and record the outcome."""
    result = run_async(_reconcile())
    logger.info("pentrix_payments_reconciled", **result)
    return result


@celery_app.task(name="pentrix.dispatch_marketing")
def dispatch_marketing_task() -> dict:
    """Every minute: send the next batch of confirmed marketing email, within the rate limit."""
    result = run_async(_dispatch_marketing())
    if any(result.values()):
        logger.info("pentrix_marketing_dispatched", **result)
    return result


@celery_app.task(name="pentrix.send_booking_reminders")
def send_booking_reminders_task() -> dict:
    result = run_async(_remind())
    if result["sent"] or result["failed"]:
        logger.info("pentrix_reminders_run", **result)
    return result
