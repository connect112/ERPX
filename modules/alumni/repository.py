import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.alumni.models import (
    AlumniEvent,
    AlumniProfile,
    EventRegistration,
    EventStatus,
    JobReferral,
    ReferralStatus,
)


class AlumniProfileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AlumniProfile:
        profile = AlumniProfile(**fields)
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def get_by_id(self, profile_id: uuid.UUID, organization_id: uuid.UUID) -> AlumniProfile | None:
        result = await self.db.execute(
            select(AlumniProfile).where(
                AlumniProfile.id == profile_id, AlumniProfile.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_student_id(self, student_id: uuid.UUID) -> AlumniProfile | None:
        result = await self.db.execute(
            select(AlumniProfile).where(AlumniProfile.student_id == student_id)
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[AlumniProfile], int]:
        conditions = [AlumniProfile.organization_id == organization_id]
        count_result = await self.db.execute(
            select(func.count()).select_from(AlumniProfile).where(*conditions)
        )
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(AlumniProfile)
            .where(*conditions)
            .order_by(AlumniProfile.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, profile: AlumniProfile, **fields) -> AlumniProfile:
        for key, value in fields.items():
            if value is not None:
                setattr(profile, key, value)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile


class AlumniEventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AlumniEvent:
        event = AlumniEvent(**fields)
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def get_by_id(self, event_id: uuid.UUID, organization_id: uuid.UUID) -> AlumniEvent | None:
        result = await self.db.execute(
            select(AlumniEvent).where(
                AlumniEvent.id == event_id, AlumniEvent.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: EventStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[AlumniEvent], int]:
        conditions = [AlumniEvent.organization_id == organization_id]
        if status is not None:
            conditions.append(AlumniEvent.status == status)
        count_result = await self.db.execute(
            select(func.count()).select_from(AlumniEvent).where(*conditions)
        )
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(AlumniEvent)
            .where(*conditions)
            .order_by(AlumniEvent.event_date.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, event: AlumniEvent, **fields) -> AlumniEvent:
        for key, value in fields.items():
            if value is not None:
                setattr(event, key, value)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def delete(self, event: AlumniEvent) -> None:
        await self.db.delete(event)
        await self.db.flush()


class EventRegistrationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> EventRegistration:
        registration = EventRegistration(**fields)
        self.db.add(registration)
        await self.db.flush()
        await self.db.refresh(registration)
        return registration

    async def get_by_event_and_alumni(
        self, event_id: uuid.UUID, alumni_id: uuid.UUID
    ) -> EventRegistration | None:
        result = await self.db.execute(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id, EventRegistration.alumni_id == alumni_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, registration_id: uuid.UUID) -> EventRegistration | None:
        result = await self.db.execute(
            select(EventRegistration).where(EventRegistration.id == registration_id)
        )
        return result.scalar_one_or_none()

    async def list_for_event(self, event_id: uuid.UUID) -> list[EventRegistration]:
        result = await self.db.execute(
            select(EventRegistration)
            .where(EventRegistration.event_id == event_id)
            .order_by(EventRegistration.registered_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_alumni(self, alumni_id: uuid.UUID) -> list[EventRegistration]:
        result = await self.db.execute(
            select(EventRegistration)
            .where(EventRegistration.alumni_id == alumni_id)
            .order_by(EventRegistration.registered_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, registration: EventRegistration, **fields) -> EventRegistration:
        for key, value in fields.items():
            if value is not None:
                setattr(registration, key, value)
        await self.db.flush()
        await self.db.refresh(registration)
        return registration


class JobReferralRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> JobReferral:
        referral = JobReferral(**fields)
        self.db.add(referral)
        await self.db.flush()
        await self.db.refresh(referral)
        return referral

    async def get_by_id(self, referral_id: uuid.UUID, organization_id: uuid.UUID) -> JobReferral | None:
        result = await self.db.execute(
            select(JobReferral).where(
                JobReferral.id == referral_id, JobReferral.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: ReferralStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[JobReferral], int]:
        conditions = [JobReferral.organization_id == organization_id]
        if status is not None:
            conditions.append(JobReferral.status == status)
        count_result = await self.db.execute(
            select(func.count()).select_from(JobReferral).where(*conditions)
        )
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(JobReferral)
            .where(*conditions)
            .order_by(JobReferral.posted_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_for_alumni(self, alumni_id: uuid.UUID) -> list[JobReferral]:
        result = await self.db.execute(
            select(JobReferral)
            .where(JobReferral.alumni_id == alumni_id)
            .order_by(JobReferral.posted_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, referral: JobReferral, **fields) -> JobReferral:
        for key, value in fields.items():
            if value is not None:
                setattr(referral, key, value)
        await self.db.flush()
        await self.db.refresh(referral)
        return referral
