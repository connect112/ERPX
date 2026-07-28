import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.backups.schemas import BackupDownloadResponse, BackupJobListResponse, BackupJobPublic
from modules.backups.service import BackupService

router = APIRouter()


@router.post("", response_model=BackupJobPublic, status_code=status.HTTP_201_CREATED)
async def trigger_backup(
    user: User = Depends(require_permissions("backups.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BackupService(db)
    job = await service.trigger_backup(user.id)
    return BackupJobPublic.model_validate(job)


@router.get("", response_model=BackupJobListResponse)
async def list_backups(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_permissions("backups.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BackupService(db)
    jobs, total = await service.list_jobs(skip=skip, limit=limit)
    return BackupJobListResponse(items=[BackupJobPublic.model_validate(j) for j in jobs], total=total)


@router.get("/{job_id}", response_model=BackupJobPublic)
async def get_backup(
    job_id: uuid.UUID,
    user: User = Depends(require_permissions("backups.view")),
    db: AsyncSession = Depends(get_db),
):
    service = BackupService(db)
    job = await service.get_job(job_id)
    return BackupJobPublic.model_validate(job)


@router.get("/{job_id}/download-url", response_model=BackupDownloadResponse)
async def get_backup_download_url(
    job_id: uuid.UUID,
    user: User = Depends(require_permissions("backups.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = BackupService(db)
    url = await service.get_download_url(job_id)
    return BackupDownloadResponse(download_url=url)
