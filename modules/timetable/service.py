import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.batches.repository import BatchRepository
from modules.classrooms.repository import ClassroomRepository
from modules.timetable.models import TimetableEntry
from modules.trainers.repository import TrainerRepository
from modules.timetable.repository import TimetableRepository

logger = get_logger(__name__)


class TimetableService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = TimetableRepository(db)
        self.batch_repo = BatchRepository(db)
        self.classroom_repo = ClassroomRepository(db)
        self.trainer_repo = TrainerRepository(db)

    async def _validate_references(
        self,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
        classroom_id: uuid.UUID | None,
        trainer_id: uuid.UUID | None,
    ) -> None:
        batch = await self.batch_repo.get_by_id(batch_id, organization_id)
        if not batch:
            raise NotFoundError("Batch", batch_id)
        if classroom_id is not None:
            classroom = await self.classroom_repo.get_by_id(classroom_id, organization_id)
            if not classroom:
                raise NotFoundError("Classroom", classroom_id)
        if trainer_id is not None:
            trainer = await self.trainer_repo.get_by_id(trainer_id, organization_id)
            if not trainer:
                raise NotFoundError("Trainer", trainer_id)

    async def create_entry(
        self,
        organization_id: uuid.UUID,
        batch_id: uuid.UUID,
        classroom_id: uuid.UUID | None,
        trainer_id: uuid.UUID | None,
        **fields,
    ) -> TimetableEntry:
        if fields["start_time"] >= fields["end_time"]:
            raise ValidationError("Start time must be before end time.")

        await self._validate_references(organization_id, batch_id, classroom_id, trainer_id)

        conflicts = await self.repo.find_conflicts(
            organization_id,
            fields["day_of_week"],
            fields["start_time"],
            fields["end_time"],
            classroom_id,
            trainer_id,
        )
        if conflicts:
            raise ConflictError(
                "This slot conflicts with an existing timetable entry for the same classroom or trainer."
            )

        entry = await self.repo.create(
            organization_id=organization_id,
            batch_id=batch_id,
            classroom_id=classroom_id,
            trainer_id=trainer_id,
            **fields,
        )
        logger.info("timetable_entry_created", entry_id=str(entry.id), batch_id=str(batch_id))
        return entry

    async def get_entry(self, entry_id: uuid.UUID, organization_id: uuid.UUID) -> TimetableEntry:
        entry = await self.repo.get_by_id(entry_id, organization_id)
        if not entry:
            raise NotFoundError("Timetable entry", entry_id)
        return entry

    async def list_for_batch(
        self, batch_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[TimetableEntry]:
        return await self.repo.list_for_batch(batch_id, organization_id)

    async def list_for_batches(
        self, batch_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[TimetableEntry]:
        return await self.repo.list_for_batches(batch_ids, organization_id)

    async def update_entry(
        self, entry_id: uuid.UUID, organization_id: uuid.UUID, **fields
    ) -> TimetableEntry:
        entry = await self.get_entry(entry_id, organization_id)

        day_of_week = fields.get("day_of_week", entry.day_of_week)
        start_time = fields.get("start_time", entry.start_time)
        end_time = fields.get("end_time", entry.end_time)
        classroom_id = fields.get("classroom_id", entry.classroom_id)
        trainer_id = fields.get("trainer_id", entry.trainer_id)

        if start_time >= end_time:
            raise ValidationError("Start time must be before end time.")

        await self._validate_references(organization_id, entry.batch_id, classroom_id, trainer_id)

        conflicts = await self.repo.find_conflicts(
            organization_id, day_of_week, start_time, end_time, classroom_id, trainer_id,
            exclude_entry_id=entry.id,
        )
        if conflicts:
            raise ConflictError(
                "This slot conflicts with an existing timetable entry for the same classroom or trainer."
            )

        updated = await self.repo.update(entry, **fields)
        logger.info("timetable_entry_updated", entry_id=str(entry_id))
        return updated

    async def delete_entry(self, entry_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        entry = await self.get_entry(entry_id, organization_id)
        await self.repo.delete(entry)
        logger.info("timetable_entry_deleted", entry_id=str(entry_id))
