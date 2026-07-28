import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.pentrix.lab_instances.models import LabInstance, LabInstanceStatus


class LabInstanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> LabInstance:
        instance = LabInstance(**fields)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def get_by_id(self, instance_id: uuid.UUID) -> LabInstance | None:
        result = await self.db.execute(select(LabInstance).where(LabInstance.id == instance_id))
        return result.scalar_one_or_none()

    async def get_active_for_student_lab(
        self, student_id: uuid.UUID, lab_id: uuid.UUID
    ) -> LabInstance | None:
        result = await self.db.execute(
            select(LabInstance).where(
                LabInstance.student_id == student_id,
                LabInstance.lab_id == lab_id,
                LabInstance.status.in_([LabInstanceStatus.PROVISIONING, LabInstanceStatus.RUNNING]),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_student(self, student_id: uuid.UUID) -> list[LabInstance]:
        result = await self.db.execute(
            select(LabInstance)
            .where(LabInstance.student_id == student_id)
            .order_by(LabInstance.started_at.desc())
        )
        return list(result.scalars().all())

    async def mark_running(
        self, instance: LabInstance, environment_ref: str, access_endpoint: str
    ) -> LabInstance:
        instance.environment_ref = environment_ref
        instance.access_endpoint = access_endpoint
        instance.status = LabInstanceStatus.RUNNING
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def mark_failed(self, instance: LabInstance) -> LabInstance:
        instance.status = LabInstanceStatus.FAILED
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def stop(self, instance: LabInstance) -> LabInstance:
        instance.status = LabInstanceStatus.STOPPED
        instance.stopped_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance
