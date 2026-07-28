import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.events.models import Event, EventType


class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Event:
        event = Event(**fields)
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def get_by_id(self, event_id: uuid.UUID, organization_id: uuid.UUID) -> Event | None:
        result = await self.db.execute(
            select(Event).where(Event.id == event_id, Event.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        event_type: EventType | None = None,
        starts_after: datetime | None = None,
        starts_before: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Event], int]:
        conditions = [Event.organization_id == organization_id]
        if event_type is not None:
            conditions.append(Event.event_type == event_type)
        if starts_after is not None:
            conditions.append(Event.start_at >= starts_after)
        if starts_before is not None:
            conditions.append(Event.start_at <= starts_before)

        count_result = await self.db.execute(select(func.count()).select_from(Event).where(*conditions))
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(Event).where(*conditions).order_by(Event.start_at.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, event: Event, **fields) -> Event:
        for key, value in fields.items():
            if value is not None:
                setattr(event, key, value)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def delete(self, event: Event) -> None:
        await self.db.delete(event)
        await self.db.flush()
