import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.backups.models import BackupJob


class BackupJobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> BackupJob:
        job = BackupJob(**fields)
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> BackupJob | None:
        result = await self.db.execute(select(BackupJob).where(BackupJob.id == job_id))
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 50) -> tuple[list[BackupJob], int]:
        count_result = await self.db.execute(select(func.count()).select_from(BackupJob))
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(BackupJob).order_by(BackupJob.started_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, job: BackupJob, **fields) -> BackupJob:
        for key, value in fields.items():
            if value is not None:
                setattr(job, key, value)
        await self.db.flush()
        await self.db.refresh(job)
        return job
