import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.workshops.models import RegistrationStatus, Workshop, WorkshopRegistration, WorkshopStatus


class WorkshopRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Workshop:
        workshop = Workshop(**fields)
        self.db.add(workshop)
        await self.db.flush()
        await self.db.refresh(workshop)
        return workshop

    async def get_by_id(self, workshop_id: uuid.UUID, organization_id: uuid.UUID) -> Workshop | None:
        result = await self.db.execute(
            select(Workshop).where(
                Workshop.id == workshop_id, Workshop.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, organization_id: uuid.UUID, code: str) -> Workshop | None:
        result = await self.db.execute(
            select(Workshop).where(Workshop.organization_id == organization_id, Workshop.code == code)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: WorkshopStatus | None = None,
        upcoming_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Workshop], int]:
        conditions = [Workshop.organization_id == organization_id]
        if status is not None:
            conditions.append(Workshop.status == status)
        if upcoming_only:
            conditions.append(Workshop.workshop_date >= date.today())

        count_result = await self.db.execute(select(func.count()).select_from(Workshop).where(*conditions))
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Workshop)
            .where(*conditions)
            .order_by(Workshop.workshop_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, workshop: Workshop, **fields) -> Workshop:
        for key, value in fields.items():
            if value is not None:
                setattr(workshop, key, value)
        await self.db.flush()
        await self.db.refresh(workshop)
        return workshop

    async def delete(self, workshop: Workshop) -> None:
        await self.db.delete(workshop)
        await self.db.flush()


class WorkshopRegistrationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> WorkshopRegistration:
        registration = WorkshopRegistration(**fields)
        self.db.add(registration)
        await self.db.flush()
        await self.db.refresh(registration)
        return registration

    async def get_by_id(self, registration_id: uuid.UUID) -> WorkshopRegistration | None:
        result = await self.db.execute(
            select(WorkshopRegistration).where(WorkshopRegistration.id == registration_id)
        )
        return result.scalar_one_or_none()

    async def get_by_workshop_and_student(
        self, workshop_id: uuid.UUID, student_id: uuid.UUID
    ) -> WorkshopRegistration | None:
        result = await self.db.execute(
            select(WorkshopRegistration).where(
                WorkshopRegistration.workshop_id == workshop_id,
                WorkshopRegistration.student_id == student_id,
            )
        )
        return result.scalar_one_or_none()

    async def count_active_for_workshop(self, workshop_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(WorkshopRegistration)
            .where(
                WorkshopRegistration.workshop_id == workshop_id,
                WorkshopRegistration.status != RegistrationStatus.CANCELLED,
            )
        )
        return result.scalar_one()

    async def list_for_workshop(self, workshop_id: uuid.UUID) -> list[WorkshopRegistration]:
        result = await self.db.execute(
            select(WorkshopRegistration)
            .where(WorkshopRegistration.workshop_id == workshop_id)
            .order_by(WorkshopRegistration.registered_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_student(self, student_id: uuid.UUID) -> list[WorkshopRegistration]:
        result = await self.db.execute(
            select(WorkshopRegistration)
            .where(WorkshopRegistration.student_id == student_id)
            .order_by(WorkshopRegistration.registered_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, registration: WorkshopRegistration, **fields) -> WorkshopRegistration:
        for key, value in fields.items():
            if value is not None:
                setattr(registration, key, value)
        await self.db.flush()
        await self.db.refresh(registration)
        return registration
