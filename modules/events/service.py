import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging_config import get_logger
from modules.events.models import Event
from modules.events.repository import EventRepository

logger = get_logger(__name__)


class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EventRepository(db)

    async def create_event(
        self, organization_id: uuid.UUID, created_by_user_id: uuid.UUID, **fields
    ) -> Event:
        event = await self.repo.create(
            organization_id=organization_id, created_by_user_id=created_by_user_id, **fields
        )
        logger.info("org_event_created", event_id=str(event.id))
        return event

    async def get_event(self, event_id: uuid.UUID, organization_id: uuid.UUID) -> Event:
        event = await self.repo.get_by_id(event_id, organization_id)
        if not event:
            raise NotFoundError("Event", event_id)
        return event

    async def list_events(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_event(self, event_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Event:
        event = await self.get_event(event_id, organization_id)
        updated = await self.repo.update(event, **fields)
        logger.info("org_event_updated", event_id=str(event_id))
        return updated

    async def delete_event(self, event_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        event = await self.get_event(event_id, organization_id)
        await self.repo.delete(event)
        logger.info("org_event_deleted", event_id=str(event_id))
