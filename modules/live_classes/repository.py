import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.live_classes.models import LiveClass, LiveClassStatus


class LiveClassRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> LiveClass:
        live_class = LiveClass(**fields)
        self.db.add(live_class)
        await self.db.flush()
        await self.db.refresh(live_class)
        return live_class

    async def get_by_id(self, live_class_id: uuid.UUID, organization_id: uuid.UUID) -> LiveClass | None:
        result = await self.db.execute(
            select(LiveClass).where(
                LiveClass.id == live_class_id, LiveClass.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID | None = None,
        status: LiveClassStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[LiveClass], int]:
        conditions = [LiveClass.organization_id == organization_id]
        if batch_id is not None:
            conditions.append(LiveClass.batch_id == batch_id)
        if status is not None:
            conditions.append(LiveClass.status == status)

        count_result = await self.db.execute(
            select(func.count()).select_from(LiveClass).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(LiveClass)
            .where(*conditions)
            .order_by(LiveClass.scheduled_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, live_class: LiveClass, **fields) -> LiveClass:
        for key, value in fields.items():
            if value is not None:
                setattr(live_class, key, value)
        await self.db.flush()
        await self.db.refresh(live_class)
        return live_class

    async def delete(self, live_class: LiveClass) -> None:
        await self.db.delete(live_class)
        await self.db.flush()
