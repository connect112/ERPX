import uuid
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.alumni.models import (
    AlumniEvent,
    AlumniProfile,
    EventRegistration,
    EventStatus,
    JobReferral,
    RegistrationStatus,
)
from modules.alumni.repository import (
    AlumniEventRepository,
    AlumniProfileRepository,
    EventRegistrationRepository,
    JobReferralRepository,
)

logger = get_logger(__name__)


class AlumniProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AlumniProfileRepository(db)

    async def create_own_profile(
        self, organization_id: uuid.UUID, student_id: uuid.UUID, **fields
    ) -> AlumniProfile:
        existing = await self.repo.get_by_student_id(student_id)
        if existing:
            raise ConflictError("You already have an alumni profile.")
        profile = await self.repo.create(organization_id=organization_id, student_id=student_id, **fields)
        logger.info("alumni_profile_created", profile_id=str(profile.id))
        return profile

    async def get_own_profile(self, student_id: uuid.UUID) -> AlumniProfile:
        profile = await self.repo.get_by_student_id(student_id)
        if not profile:
            raise NotFoundError("Alumni profile", student_id)
        return profile

    async def update_own_profile(self, student_id: uuid.UUID, **fields) -> AlumniProfile:
        profile = await self.get_own_profile(student_id)
        updated = await self.repo.update(profile, **fields)
        logger.info("alumni_profile_updated", profile_id=str(profile.id))
        return updated

    async def get_profile(self, profile_id: uuid.UUID, organization_id: uuid.UUID) -> AlumniProfile:
        profile = await self.repo.get_by_id(profile_id, organization_id)
        if not profile:
            raise NotFoundError("Alumni profile", profile_id)
        return profile

    async def list_profiles(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def set_verified(
        self, profile_id: uuid.UUID, organization_id: uuid.UUID, is_verified: bool
    ) -> AlumniProfile:
        profile = await self.get_profile(profile_id, organization_id)
        profile.is_verified = is_verified
        await self.db.flush()
        await self.db.refresh(profile)
        logger.info("alumni_profile_verification_changed", profile_id=str(profile_id), is_verified=is_verified)
        return profile


class AlumniEventService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AlumniEventRepository(db)

    async def create_event(self, organization_id: uuid.UUID, **fields) -> AlumniEvent:
        event = await self.repo.create(organization_id=organization_id, **fields)
        logger.info("alumni_event_created", event_id=str(event.id))
        return event

    async def get_event(self, event_id: uuid.UUID, organization_id: uuid.UUID) -> AlumniEvent:
        event = await self.repo.get_by_id(event_id, organization_id)
        if not event:
            raise NotFoundError("Alumni event", event_id)
        return event

    async def list_events(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def update_event(self, event_id: uuid.UUID, organization_id: uuid.UUID, **fields) -> AlumniEvent:
        event = await self.get_event(event_id, organization_id)
        updated = await self.repo.update(event, **fields)
        logger.info("alumni_event_updated", event_id=str(event_id))
        return updated

    async def change_status(
        self, event_id: uuid.UUID, organization_id: uuid.UUID, status: EventStatus
    ) -> AlumniEvent:
        event = await self.get_event(event_id, organization_id)
        updated = await self.repo.update(event, status=status)
        logger.info("alumni_event_status_changed", event_id=str(event_id), status=status.value)
        return updated

    async def delete_event(self, event_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        event = await self.get_event(event_id, organization_id)
        await self.repo.delete(event)
        logger.info("alumni_event_deleted", event_id=str(event_id))


class EventRegistrationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = EventRegistrationRepository(db)
        self.event_repo = AlumniEventRepository(db)

    async def register(
        self, organization_id: uuid.UUID, event_id: uuid.UUID, alumni_id: uuid.UUID
    ) -> EventRegistration:
        event = await self.event_repo.get_by_id(event_id, organization_id)
        if not event:
            raise NotFoundError("Alumni event", event_id)
        if event.status != EventStatus.PUBLISHED:
            raise ValidationError("This event is not currently open for registration.")
        if event.registration_deadline and date.today() > event.registration_deadline:
            raise ValidationError("The registration deadline for this event has passed.")

        existing = await self.repo.get_by_event_and_alumni(event_id, alumni_id)
        if existing:
            raise ConflictError("You have already registered for this event.")

        registration = await self.repo.create(
            event_id=event_id, alumni_id=alumni_id, registered_at=datetime.now(timezone.utc)
        )
        logger.info("alumni_event_registration_created", registration_id=str(registration.id))
        return registration

    async def list_for_event(self, event_id: uuid.UUID, organization_id: uuid.UUID):
        event = await self.event_repo.get_by_id(event_id, organization_id)
        if not event:
            raise NotFoundError("Alumni event", event_id)
        return await self.repo.list_for_event(event_id)

    async def list_for_alumni(self, alumni_id: uuid.UUID):
        return await self.repo.list_for_alumni(alumni_id)

    async def mark_attendance(
        self, registration_id: uuid.UUID, status: RegistrationStatus
    ) -> EventRegistration:
        registration = await self.repo.get_by_id(registration_id)
        if not registration:
            raise NotFoundError("Registration", registration_id)
        updated = await self.repo.update(registration, status=status)
        logger.info("alumni_registration_status_changed", registration_id=str(registration_id), status=status.value)
        return updated


class JobReferralService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = JobReferralRepository(db)

    async def create_referral(
        self, organization_id: uuid.UUID, alumni_id: uuid.UUID, **fields
    ) -> JobReferral:
        referral = await self.repo.create(
            organization_id=organization_id,
            alumni_id=alumni_id,
            posted_at=datetime.now(timezone.utc),
            **fields,
        )
        logger.info("alumni_job_referral_created", referral_id=str(referral.id))
        return referral

    async def get_referral(self, referral_id: uuid.UUID, organization_id: uuid.UUID) -> JobReferral:
        referral = await self.repo.get_by_id(referral_id, organization_id)
        if not referral:
            raise NotFoundError("Job referral", referral_id)
        return referral

    async def list_referrals(self, organization_id: uuid.UUID, **filters):
        return await self.repo.list_for_organization(organization_id, **filters)

    async def list_for_alumni(self, alumni_id: uuid.UUID):
        return await self.repo.list_for_alumni(alumni_id)

    async def update_referral(
        self, referral_id: uuid.UUID, organization_id: uuid.UUID, alumni_id: uuid.UUID, **fields
    ) -> JobReferral:
        referral = await self.get_referral(referral_id, organization_id)
        if referral.alumni_id != alumni_id:
            raise NotFoundError("Job referral", referral_id)
        updated = await self.repo.update(referral, **fields)
        logger.info("alumni_job_referral_updated", referral_id=str(referral_id))
        return updated
