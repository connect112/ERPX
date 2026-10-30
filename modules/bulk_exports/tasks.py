"""
Bulk downloads -- background tasks: prepare one ZIP, and remove the ones that have expired.
"""

import uuid

from app.core.audit_context import set_audit_organization, set_audit_user
from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.db.session import get_db_context, run_async
from modules.bulk_exports.models import BulkExportJob
from modules.bulk_exports.service import BulkExportService

logger = get_logger(__name__)


async def _run(job_id: uuid.UUID) -> None:
    async with get_db_context() as db:
        job = await db.get(BulkExportJob, job_id)
        if job is None:
            logger.warning("bulk_export_job_missing", job_id=str(job_id))
            return
        # Changes the worker makes are recorded in the audit trail as the requester's, in their organization.
        set_audit_user(job.requested_by_user_id)
        set_audit_organization(job.organization_id)
        await BulkExportService(db).run(job, db.commit, commits=True)


async def _cleanup() -> dict[str, int]:
    async with get_db_context() as db:
        return await BulkExportService(db).cleanup()


@celery_app.task(name="bulk_exports.run", acks_late=True)
def run_bulk_export_task(job_id: str) -> None:
    run_async(_run(uuid.UUID(job_id)))


@celery_app.task(name="bulk_exports.cleanup")
def cleanup_bulk_exports_task() -> dict[str, int]:
    result = run_async(_cleanup())
    if any(result.values()):
        logger.info("bulk_export_cleanup", **result)
    return result
