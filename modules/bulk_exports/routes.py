"""
Bulk downloads. Signed-in staff only; each document type applies its own module's permission (see sources/), and every
job, link and file is visible only to the person who asked for it, inside their own organization.
"""

import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.limiter import limiter
from app.core.logging_config import get_logger
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.bulk_exports.filenames import TemplateError
from modules.bulk_exports.models import BulkExportJob, ExportStatus
from modules.bulk_exports.schemas import (
    DownloadOut,
    ItemOut,
    ItemsPage,
    JobCreateRequest,
    JobOut,
    PreviewOut,
    PreviewRequest,
    SourceInfo,
)
from modules.bulk_exports.service import BulkExportService
from modules.bulk_exports.sources import SOURCES
from modules.users.dependencies import get_current_user_organization_id

logger = get_logger(__name__)

router = APIRouter()


def _job_out(job: BulkExportJob) -> JobOut:
    out = JobOut.model_validate(job)
    source = SOURCES.get(job.source)
    out.source_label = source.label if source else job.source
    return out


@router.get("/sources/{source}", response_model=SourceInfo)
async def source_info(
    source: str,
    scope_id: uuid.UUID | None = None,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """The placeholders (including this module's own fields), presets and filters for one kind of document."""
    service = BulkExportService(db)
    src, scope = await service.open(source, user, organization_id, scope_id)
    return await service.describe(src, scope)


@router.get("/sources/{source}/items", response_model=ItemsPage)
async def list_items(
    source: str,
    scope_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, max_length=200),
    status_filter: str | None = Query(default=None, alias="status", max_length=60),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """One page of the documents that can be downloaded."""
    service = BulkExportService(db)
    src, scope = await service.open(source, user, organization_id, scope_id)
    items, total = await service.list_items(src, scope, search, status_filter, page, page_size)
    return ItemsPage(
        items=[ItemOut(id=i.id, title=i.title, subtitle=i.subtitle, status=i.status) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/preview", response_model=PreviewOut)
async def preview_names(
    payload: PreviewRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """The ZIP name and the first file names the chosen format gives, or why the format cannot be used."""
    service = BulkExportService(db)
    src, scope = await service.open(payload.source, user, organization_id, payload.scope_id)
    try:
        result = await service.preview(
            src, scope, payload.options.model_dump(), payload.selection.model_dump() if payload.selection else None
        )
    except TemplateError as exc:
        return PreviewOut(valid=False, error=str(exc))
    return PreviewOut(valid=True, **result)


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_job(
    request: Request,
    payload: JobCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a download. A small selection is zipped straight away; a larger one is prepared in the background."""
    from app.core.exceptions import ValidationError

    service = BulkExportService(db)
    try:
        job = await service.create_job(
            user, organization_id, payload.source, payload.scope_id, payload.selection.model_dump(), payload.options.model_dump()
        )
    except TemplateError as exc:
        raise ValidationError(str(exc)) from exc
    if job.total_items <= settings.BULK_EXPORT_INLINE_MAX_ITEMS:
        await service.run(job, db.flush)
        return _job_out(job)
    # The worker reads the job from the database, so it must be committed before the task is queued.
    await db.commit()
    from modules.bulk_exports.tasks import run_bulk_export_task

    try:
        run_bulk_export_task.apply_async(args=[str(job.id)], retry=False)
    except Exception as exc:  # noqa: BLE001 - broker down: say so, and do not leave a job that will never run
        logger.warning("bulk_export_enqueue_failed", job_id=str(job.id), exc_info=True)
        job.status = ExportStatus.FAILED.value
        job.error = "The download could not be queued. Please try again in a moment."
        await db.flush()
        raise ServiceUnavailableError("The download could not be queued. Please try again in a moment.") from exc
    return _job_out(job)


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Your recent downloads: being prepared, ready, failed and expired."""
    return [_job_out(j) for j in await BulkExportService(db).list_jobs(user, organization_id)]


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return _job_out(await BulkExportService(db).get_job(user, organization_id, job_id))


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(
    job_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return _job_out(await BulkExportService(db).cancel(user, organization_id, job_id))


@router.post("/jobs/{job_id}/download", response_model=DownloadOut)
async def download_job(
    job_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """A link to the ZIP, signed for a few minutes. Every link handed out is counted on the job (and audited)."""
    url, job = await BulkExportService(db).download_link(user, organization_id, job_id)
    return DownloadOut(url=url, filename=job.zip_filename or "documents.zip", expires_in_seconds=settings.BULK_EXPORT_LINK_MINUTES * 60)


@router.delete("/jobs/{job_id}/file", response_model=JobOut)
async def discard_file(
    job_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove the ZIP now rather than when it expires. The job stays in the list as a record."""
    return _job_out(await BulkExportService(db).discard(user, organization_id, job_id))
