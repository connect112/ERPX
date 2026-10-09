"""
Placements module -- background tasks.

Refreshes each organisation's job feed (jobs from outside job sites) a few times a day. Organisations opt in by
opening the Job Feed page once (that creates their settings); each source is read at most as often as it allows.
"""

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
                    await service.refresh(organization_id)
                    await service.clear_stale(organization_id)
                refreshed += 1
            except Exception:  # noqa: BLE001 - one organisation's trouble must not stop the others
                logger.warning("job_feed_refresh_failed", organization_id=str(organization_id), exc_info=True)
    return refreshed


@celery_app.task(name="placements.refresh_job_feed")
def refresh_job_feed_task() -> int:
    return run_async(_refresh_all())
