"""
Pentrix operations: scheduled tasks.

* pentrix.sync_bookings (every minute): pull what Pentrix changed. Pentrix also tells ERPX straight away when something changes; this
  pull is what guarantees nothing is missed if that message never arrived.
* pentrix.send_booking_reminders (every minute): send the reminder emails that are due (see reminders.py).
"""
from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.pentrix_ops.client import PentrixClient
from modules.pentrix_ops.reminders import send_due_reminders
from modules.pentrix_ops.service import PentrixBookingService

logger = get_logger(__name__)


async def _sync() -> int:
    if not PentrixClient.configured():
        return 0
    async with get_db_context() as db:
        return await PentrixBookingService(db).sync()


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


@celery_app.task(name="pentrix.send_booking_reminders")
def send_booking_reminders_task() -> dict:
    result = run_async(_remind())
    if result["sent"] or result["failed"]:
        logger.info("pentrix_reminders_run", **result)
    return result
