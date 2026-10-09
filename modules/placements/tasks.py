"""
Placements module -- background tasks.

Refreshes each organisation's job feed (jobs from outside job sites) a few times a day. Organisations opt in by
opening the Job Feed page once (that creates their settings); each source is read at most as often as it allows.
"""

import uuid

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.placements.job_feed import JobFeedService

logger = get_logger(__name__)


async def _refresh_all() -> int:
    refreshed = 0
    async with get_db_context() as db:
        service = JobFeedService(db)
        for organization_id in await service.organizations_with_feed():
            try:
                async with db.begin_nested():
                    await service.run_refresh(organization_id)
                refreshed += 1
            except Exception:  # noqa: BLE001 - one organisation's trouble must not stop the others
                logger.warning("job_feed_refresh_failed", organization_id=str(organization_id), exc_info=True)
    return refreshed


async def _refresh_one(organization_id: uuid.UUID, force: bool) -> None:
    async with get_db_context() as db:
        await JobFeedService(db).run_refresh(organization_id, force=force)


@celery_app.task(name="placements.refresh_job_feed_org", ignore_result=True)
def refresh_job_feed_org_task(organization_id: str, force: bool = False) -> None:
    run_async(_refresh_one(uuid.UUID(organization_id), force))


def enqueue_job_feed_refresh(organization_id: uuid.UUID) -> bool:
    """Queue one organisation's refresh (it can take a minute or two); never raises."""
    try:
        refresh_job_feed_org_task.apply_async(args=[str(organization_id)], retry=False)
    except Exception:  # noqa: BLE001 - broker trouble
        logger.warning("job_feed_enqueue_failed", organization_id=str(organization_id), exc_info=True)
        return False
    return True


@celery_app.task(name="placements.refresh_job_feed")
def refresh_job_feed_task() -> int:
    return run_async(_refresh_all())
