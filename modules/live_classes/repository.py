import uuid

from sqlalchemy import func, or_, select
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

    async def list_for_batches(
        self, batch_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[LiveClass]:
        if not batch_ids:
            return []
        result = await self.db.execute(
            select(LiveClass)
            .where(
                LiveClass.batch_id.in_(batch_ids),
                LiveClass.organization_id == organization_id,
            )
            .order_by(LiveClass.scheduled_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_trainer(
        self, trainer_id: uuid.UUID, batch_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[LiveClass]:
        """Every live class this trainer should see: either scheduled for a
        batch they teach (batches.trainer_id), or explicitly assigned to
        them on the class itself (live_classes.trainer_id) even when the
        batch has no trainer of its own set. The two aren't always the
        same — an admin can pick a trainer per class independently of
        whichever trainer (if any) is assigned to the batch as a whole —
        so this must be an OR, not just batch membership. Missing the
        live_classes.trainer_id branch was a real bug: a trainer a class
        was explicitly scheduled for couldn't see it at all when the
        batch itself had no trainer assigned."""
        conditions = [LiveClass.trainer_id == trainer_id]
        if batch_ids:
            conditions.append(LiveClass.batch_id.in_(batch_ids))
        result = await self.db.execute(
            select(LiveClass)
            .where(or_(*conditions), LiveClass.organization_id == organization_id)
            .order_by(LiveClass.scheduled_at.desc())
        )
        return list(result.scalars().all())

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
