"""Celery tasks for internship onboarding (autodiscovered)."""

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.internship_onboarding.emails import send_invitation_task  # noqa: F401

logger = get_logger(__name__)


async def _reconcile() -> dict[str, int]:
    """Ask the gateway about orders still open after a while, in case a notification never arrived."""
    from app.core.config import settings
    from modules.internship_onboarding.payments import PaymentService
    from modules.internship_onboarding.providers import ProviderError

    if not settings.CASHFREE_ENABLED:
        return {"checked": 0, "confirmed": 0}
    checked = confirmed = 0
    async with get_db_context() as db:
        ids = [o.id for o in await PaymentService(db).stale_orders()]
    for order_id in ids:
        async with get_db_context() as db:
            from modules.internship_onboarding.models import PaymentOrder

            order = await db.get(PaymentOrder, order_id, with_for_update=True)
            if order is None or order.status != "active":
                continue
            try:
                outcome = await PaymentService(db).refresh_order(order)
            except ProviderError:
                logger.warning("onboarding_reconcile_failed", order_id=str(order_id))
                continue
            checked += 1
            confirmed += outcome == "confirmed"
    return {"checked": checked, "confirmed": confirmed}


@celery_app.task(name="internship_onboarding.reconcile_payments")
def reconcile_payments_task() -> dict[str, int]:
    result = run_async(_reconcile())
    if result["checked"]:
        logger.info("onboarding_reconcile", **result)
    return result
