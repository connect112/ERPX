import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.batches.repository import BatchRepository
from modules.live_classes.models import LiveClass, LiveClassStatus
from modules.live_classes.repository import LiveClassRepository
from modules.trainers.repository import TrainerRepository

logger = get_logger(__name__)

_ALLOWED_TRANSITIONS: dict[LiveClassStatus, set[LiveClassStatus]] = {
    LiveClassStatus.SCHEDULED: {LiveClassStatus.LIVE, LiveClassStatus.CANCELLED},
    LiveClassStatus.LIVE: {LiveClassStatus.COMPLETED, LiveClassStatus.CANCELLED},
    LiveClassStatus.COMPLETED: set(),
    LiveClassStatus.CANCELLED: set(),
}


class LiveClassService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LiveClassRepository(db)
        self.batch_repo = BatchRepository(db)
        self.trainer_repo = TrainerRepository(db)

    async def create_live_class(
        self,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
        trainer_id: uuid.UUID | None,
        **fields,
    ) -> LiveClass:
        batch = await self.batch_repo.get_by_id(batch_id, organization_id)
        if not batch:
            raise NotFoundError("Batch", batch_id)
        if trainer_id is not None:
            trainer = await self.trainer_repo.get_by_id(trainer_id, organization_id)
            if not trainer:
                raise NotFoundError("Trainer", trainer_id)

        live_class = await self.repo.create(
            organization_id=organization_id, batch_id=batch_id, trainer_id=trainer_id, **fields
        )
        logger.info("live_class_created", live_class_id=str(live_class.id), batch_id=str(batch_id))
        return live_class

    async def get_live_class(self, live_class_id: uuid.UUID, organization_id: uuid.UUID) -> LiveClass:
        live_class = await self.repo.get_by_id(live_class_id, organization_id)
        if not live_class:
            raise NotFoundError("Live class", live_class_id)
        return live_class

    async def list_live_classes(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_live_class(
        self, live_class_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> LiveClass:
        live_class = await self.get_live_class(live_class_id, organization_id)
        updated = await self.repo.update(live_class, **fields)
        logger.info("live_class_updated", live_class_id=str(live_class_id))
        return updated

    async def change_status(
        self,
        live_class_id: uuid.UUID,
        organization_id: uuid.UUID,
        new_status: LiveClassStatus,
        recording_url: str | None = None,
    ) -> LiveClass:
        live_class = await self.get_live_class(live_class_id, organization_id)
        allowed = _ALLOWED_TRANSITIONS[live_class.status]
        if new_status not in allowed:
            raise ValidationError(
                f"Cannot transition a live class from '{live_class.status.value}' to '{new_status.value}'."
            )

        live_class.status = new_status
        if new_status == LiveClassStatus.COMPLETED and recording_url:
            live_class.recording_url = recording_url
        await self.db.flush()
        await self.db.refresh(live_class)
        logger.info("live_class_status_changed", live_class_id=str(live_class_id), status=new_status.value)
        return live_class

    async def delete_live_class(self, live_class_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        live_class = await self.get_live_class(live_class_id, organization_id)
        await self.repo.delete(live_class)
        logger.info("live_class_deleted", live_class_id=str(live_class_id))
