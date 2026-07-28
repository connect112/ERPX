import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.students.repository import StudentRepository
from modules.trainers.repository import TrainerRepository
from modules.workshops.models import RegistrationStatus, Workshop, WorkshopRegistration, WorkshopStatus
from modules.workshops.repository import WorkshopRegistrationRepository, WorkshopRepository

logger = get_logger(__name__)


class WorkshopService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WorkshopRepository(db)
        self.trainer_repo = TrainerRepository(db)

    async def create_workshop(
        self, organization_id: uuid.UUID, code: str, trainer_id: uuid.UUID | None = None, **fields
    ) -> Workshop:
        if trainer_id is not None:
            trainer = await self.trainer_repo.get_by_id(trainer_id, organization_id)
            if not trainer:
                raise NotFoundError("Trainer", trainer_id)

        existing = await self.repo.get_by_code(organization_id, code)
        if existing:
            raise ConflictError(f"A workshop with code '{code}' already exists.")

        workshop = await self.repo.create(
            organization_id=organization_id, code=code, trainer_id=trainer_id, **fields
        )
        logger.info("workshop_created", workshop_id=str(workshop.id))
        return workshop

    async def get_workshop(self, workshop_id: uuid.UUID, organization_id: uuid.UUID) -> Workshop:
        workshop = await self.repo.get_by_id(workshop_id, organization_id)
        if not workshop:
            raise NotFoundError("Workshop", workshop_id)
        return workshop

    async def list_workshops(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_workshop(self, workshop_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> Workshop:
        workshop = await self.get_workshop(workshop_id, organization_id)
        updated = await self.repo.update(workshop, **fields)
        logger.info("workshop_updated", workshop_id=str(workshop_id))
        return updated

    async def change_status(
        self, workshop_id: uuid.UUID, organization_id: uuid.UUID, status: WorkshopStatus
    ) -> Workshop:
        workshop = await self.get_workshop(workshop_id, organization_id)
        updated = await self.repo.update(workshop, status=status)
        logger.info("workshop_status_changed", workshop_id=str(workshop_id), status=status.value)
        return updated

    async def delete_workshop(self, workshop_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        workshop = await self.get_workshop(workshop_id, organization_id)
        await self.repo.delete(workshop)
        logger.info("workshop_deleted", workshop_id=str(workshop_id))


class WorkshopRegistrationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WorkshopRegistrationRepository(db)
        self.workshop_repo = WorkshopRepository(db)
        self.student_repo = StudentRepository(db)

    async def register(
        self,
        organization_id: uuid.UUID,
        workshop_id: uuid.UUID,
        contact_name: str,
        student_id: uuid.UUID | None = None,
        contact_email: str | None = None,
        contact_phone: str | None = None,
    ) -> WorkshopRegistration:
        workshop = await self.workshop_repo.get_by_id(workshop_id, organization_id)
        if not workshop:
            raise NotFoundError("Workshop", workshop_id)
        if workshop.status not in (WorkshopStatus.PUBLISHED, WorkshopStatus.ONGOING):
            raise ValidationError("This workshop is not open for registration.")

        if student_id is not None:
            student = await self.student_repo.get_by_id(student_id, organization_id)
            if not student:
                raise NotFoundError("Student", student_id)
            existing = await self.repo.get_by_workshop_and_student(workshop_id, student_id)
            if existing:
                raise ConflictError("This student is already registered for this workshop.")

        if workshop.capacity is not None:
            active_count = await self.repo.count_active_for_workshop(workshop_id)
            if active_count >= workshop.capacity:
                raise ValidationError("This workshop has reached its registration capacity.")

        registration = await self.repo.create(
            workshop_id=workshop_id,
            student_id=student_id,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            registered_at=datetime.now(timezone.utc),
            is_paid=workshop.fee == 0,
        )
        logger.info("workshop_registration_created", registration_id=str(registration.id))
        return registration

    async def list_for_workshop(self, workshop_id: uuid.UUID, organization_id: uuid.UUID):
        await self._get_owned_workshop(workshop_id, organization_id)
        return await self.repo.list_for_workshop(workshop_id)

    async def list_for_student(self, student_id: uuid.UUID) -> list[WorkshopRegistration]:
        return await self.repo.list_for_student(student_id)

    async def _get_owned_workshop(self, workshop_id: uuid.UUID, organization_id: uuid.UUID) -> Workshop:
        workshop = await self.workshop_repo.get_by_id(workshop_id, organization_id)
        if not workshop:
            raise NotFoundError("Workshop", workshop_id)
        return workshop

    async def mark_attendance(
        self, registration_id: uuid.UUID, organization_id: uuid.UUID, attended: bool
    ) -> WorkshopRegistration:
        registration = await self.repo.get_by_id(registration_id)
        if not registration:
            raise NotFoundError("Workshop registration", registration_id)
        await self._get_owned_workshop(registration.workshop_id, organization_id)
        status = RegistrationStatus.ATTENDED if attended else RegistrationStatus.NO_SHOW
        updated = await self.repo.update(registration, status=status)
        logger.info("workshop_attendance_marked", registration_id=str(registration_id), attended=attended)
        return updated

    async def cancel_registration(
        self, registration_id: uuid.UUID, organization_id: uuid.UUID
    ) -> WorkshopRegistration:
        registration = await self.repo.get_by_id(registration_id)
        if not registration:
            raise NotFoundError("Workshop registration", registration_id)
        await self._get_owned_workshop(registration.workshop_id, organization_id)
        updated = await self.repo.update(registration, status=RegistrationStatus.CANCELLED)
        logger.info("workshop_registration_cancelled", registration_id=str(registration_id))
        return updated
