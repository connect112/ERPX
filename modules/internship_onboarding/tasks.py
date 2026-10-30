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


async def _follow_up(application_id) -> str:
    from modules.internship_onboarding.completion import follow_up

    async with get_db_context() as db:
        return await follow_up(db, application_id)


@celery_app.task(name="internship_onboarding.follow_up", bind=True, max_retries=3, default_retry_delay=60)
def follow_up_task(self, application_id: str) -> str:
    import uuid

    try:
        return run_async(_follow_up(uuid.UUID(application_id)))
    except Exception as exc:  # noqa: BLE001 - the sweep retries too
        logger.warning("onboarding_follow_up_failed", application_id=application_id, exc_info=True)
        raise self.retry(exc=exc) from exc


def enqueue_follow_up(application_id) -> None:
    """After the request commits (a short delay), never blocking or failing the caller."""
    try:
        follow_up_task.apply_async(args=[str(application_id)], countdown=10, retry=False)
    except Exception:  # noqa: BLE001 - the periodic sweep catches it
        logger.warning("onboarding_follow_up_enqueue_failed", application_id=str(application_id), exc_info=True)


async def _sweep() -> dict[str, int]:
    from modules.internship_onboarding.completion import sweep

    async with get_db_context() as db:
        return await sweep(db)


@celery_app.task(name="internship_onboarding.sweep")
def sweep_task() -> dict[str, int]:
    result = run_async(_sweep())
    if any(result.values()):
        logger.info("onboarding_sweep", **result)
    return result
