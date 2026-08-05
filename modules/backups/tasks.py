"""
Backups module — background tasks.

Ensures a backup exists on a schedule rather than only when a human
remembers to click "Trigger Backup" in the admin UI — see
docs/project-hardening-audit.md finding #3. `triggered_by_user_id=None`
records this run as system-initiated (the column is nullable —
`modules/backups/models.py` — specifically for this case, rather than
inventing a synthetic "system user" account). Wire into Celery beat, e.g.:

    celery_app.conf.beat_schedule["backups-trigger-daily"] = {
        "task": "backups.trigger_daily_backup",
        "schedule": crontab(hour=2, minute=0),
    }
"""

from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.backups.models import BackupStatus
from modules.backups.service import BackupService

logger = get_logger(__name__)


async def _trigger_scheduled_backup() -> BackupStatus:
    async with get_db_context() as db:
        service = BackupService(db)
        job = await service.trigger_backup(triggered_by_user_id=None)
        return job.status


@celery_app.task(name="backups.trigger_daily_backup")
def trigger_daily_backup_task() -> None:
    status = run_async(_trigger_scheduled_backup())
    logger.info("scheduled_backup_completed", status=status.value)
