import uuid
from datetime import time

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.timetable.models import DayOfWeek, TimetableEntry


class TimetableRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> TimetableEntry:
        entry = TimetableEntry(**fields)
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def get_by_id(self, entry_id: uuid.UUID, organization_id: uuid.UUID) -> TimetableEntry | None:
        result = await self.db.execute(
            select(TimetableEntry).where(
                TimetableEntry.id == entry_id, TimetableEntry.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_batch(self, batch_id: uuid.UUID, organization_id: uuid.UUID) -> list[TimetableEntry]:
        result = await self.db.execute(
            select(TimetableEntry)
            .where(
                TimetableEntry.batch_id == batch_id,
                TimetableEntry.organization_id == organization_id,
            )
            .order_by(TimetableEntry.day_of_week, TimetableEntry.start_time)
        )
        return list(result.scalars().all())

    async def find_conflicts(
        self,
        organization_id: uuid.UUID,
        day_of_week: DayOfWeek,
        start_time: time,
        end_time: time,
        classroom_id: uuid.UUID | None,
        trainer_id: uuid.UUID | None,
        exclude_entry_id: uuid.UUID | None = None,
    ) -> list[TimetableEntry]:
        if classroom_id is None and trainer_id is None:
            return []

        resource_conditions = []
        if classroom_id is not None:
            resource_conditions.append(TimetableEntry.classroom_id == classroom_id)
        if trainer_id is not None:
            resource_conditions.append(TimetableEntry.trainer_id == trainer_id)

        conditions = [
            TimetableEntry.organization_id == organization_id,
            TimetableEntry.day_of_week == day_of_week,
            or_(*resource_conditions),
            # Two ranges [a, b) and [c, d) overlap iff a < d and c < b.
            TimetableEntry.start_time < end_time,
            TimetableEntry.end_time > start_time,
        ]
        if exclude_entry_id is not None:
            conditions.append(TimetableEntry.id != exclude_entry_id)

        result = await self.db.execute(select(TimetableEntry).where(*conditions))
        return list(result.scalars().all())

    async def update(self, entry: TimetableEntry, **fields) -> TimetableEntry:
        for key, value in fields.items():
            if value is not None:
                setattr(entry, key, value)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def delete(self, entry: TimetableEntry) -> None:
        await self.db.delete(entry)
        await self.db.flush()
