import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.alumni.models import EventStatus, ReferralStatus
from modules.alumni.schemas import (
    AlumniEventCreateRequest,
    AlumniEventListResponse,
    AlumniEventPublic,
    AlumniEventStatusChangeRequest,
    AlumniEventUpdateRequest,
    AlumniProfileCreateRequest,
    AlumniProfileListResponse,
    AlumniProfilePublic,
    AlumniProfileUpdateRequest,
    AlumniProfileVerifyRequest,
    EventRegistrationAttendanceRequest,
    EventRegistrationPublic,
    JobReferralCreateRequest,
    JobReferralListResponse,
    JobReferralPublic,
    JobReferralUpdateRequest,
    MessageResponse,
)
from modules.alumni.service import (
    AlumniEventService,
    AlumniProfileService,
    EventRegistrationService,
    JobReferralService,
)
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


# ---- Student/alumni self-service: own profile ----


@router.post("/me", response_model=AlumniProfilePublic, status_code=status.HTTP_201_CREATED)
async def create_own_profile(
    payload: AlumniProfileCreateRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniProfileService(db)
    profile = await service.create_own_profile(
        student.organization_id, student.id, **payload.model_dump()
    )
    return AlumniProfilePublic.model_validate(profile)


@router.get("/me", response_model=AlumniProfilePublic)
async def get_own_profile(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniProfileService(db)
    profile = await service.get_own_profile(student.id)
    return AlumniProfilePublic.model_validate(profile)


@router.patch("/me", response_model=AlumniProfilePublic)
async def update_own_profile(
    payload: AlumniProfileUpdateRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniProfileService(db)
    profile = await service.update_own_profile(
        student.id, **payload.model_dump(exclude_unset=True)
    )
    return AlumniProfilePublic.model_validate(profile)


# ---- Student/alumni self-service: events ----


@router.get("/events/me", response_model=list[AlumniEventPublic])
async def list_published_events(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniEventService(db)
    events, _total = await service.list_events(
        student.organization_id, status=EventStatus.PUBLISHED, skip=0, limit=200
    )
    return [AlumniEventPublic.model_validate(e) for e in events]


@router.get("/events/me/registrations", response_model=list[EventRegistrationPublic])
async def list_own_registrations(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile_service = AlumniProfileService(db)
    profile = await profile_service.get_own_profile(student.id)
    registration_service = EventRegistrationService(db)
    registrations = await registration_service.list_for_alumni(profile.id)
    return [EventRegistrationPublic.model_validate(r) for r in registrations]


@router.post(
    "/events/{event_id}/register/me",
    response_model=EventRegistrationPublic,
    status_code=status.HTTP_201_CREATED,
)
async def register_for_event(
    event_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile_service = AlumniProfileService(db)
    profile = await profile_service.get_own_profile(student.id)
    registration_service = EventRegistrationService(db)
    registration = await registration_service.register(student.organization_id, event_id, profile.id)
    return EventRegistrationPublic.model_validate(registration)


# ---- Student/alumni self-service: job referrals ----


@router.get("/referrals", response_model=list[JobReferralPublic])
async def browse_open_referrals(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = JobReferralService(db)
    referrals, _total = await service.list_referrals(
        student.organization_id, status=ReferralStatus.OPEN, skip=0, limit=200
    )
    return [JobReferralPublic.model_validate(r) for r in referrals]


@router.post("/referrals/me", response_model=JobReferralPublic, status_code=status.HTTP_201_CREATED)
async def create_own_referral(
    payload: JobReferralCreateRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile_service = AlumniProfileService(db)
    profile = await profile_service.get_own_profile(student.id)
    referral_service = JobReferralService(db)
    referral = await referral_service.create_referral(
        student.organization_id, profile.id, **payload.model_dump()
    )
    return JobReferralPublic.model_validate(referral)


@router.get("/referrals/me", response_model=list[JobReferralPublic])
async def list_own_referrals(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile_service = AlumniProfileService(db)
    profile = await profile_service.get_own_profile(student.id)
    referral_service = JobReferralService(db)
    referrals = await referral_service.list_for_alumni(profile.id)
    return [JobReferralPublic.model_validate(r) for r in referrals]


@router.patch("/referrals/me/{referral_id}", response_model=JobReferralPublic)
async def update_own_referral(
    referral_id: uuid.UUID,
    payload: JobReferralUpdateRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    profile_service = AlumniProfileService(db)
    profile = await profile_service.get_own_profile(student.id)
    referral_service = JobReferralService(db)
    referral = await referral_service.update_referral(
        referral_id, student.organization_id, profile.id, **payload.model_dump(exclude_unset=True)
    )
    return JobReferralPublic.model_validate(referral)


# ---- Staff: alumni profiles ----


@router.get("/profiles", response_model=AlumniProfileListResponse)
async def list_profiles(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniProfileService(db)
    profiles, total = await service.list_profiles(organization_id, skip=skip, limit=limit)
    return AlumniProfileListResponse(
        items=[AlumniProfilePublic.model_validate(p) for p in profiles], total=total
    )


@router.get("/profiles/{profile_id}", response_model=AlumniProfilePublic)
async def get_profile(
    profile_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniProfileService(db)
    profile = await service.get_profile(profile_id, organization_id)
    return AlumniProfilePublic.model_validate(profile)


@router.post("/profiles/{profile_id}/verify", response_model=AlumniProfilePublic)
async def verify_profile(
    profile_id: uuid.UUID,
    payload: AlumniProfileVerifyRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniProfileService(db)
    profile = await service.set_verified(profile_id, organization_id, payload.is_verified)
    return AlumniProfilePublic.model_validate(profile)


# ---- Staff: alumni events ----


@router.post("/events", response_model=AlumniEventPublic, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: AlumniEventCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniEventService(db)
    event = await service.create_event(organization_id, **payload.model_dump())
    return AlumniEventPublic.model_validate(event)


@router.get("/events", response_model=AlumniEventListResponse)
async def list_events(
    status_filter: EventStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniEventService(db)
    events, total = await service.list_events(
        organization_id, status=status_filter, skip=skip, limit=limit
    )
    return AlumniEventListResponse(items=[AlumniEventPublic.model_validate(e) for e in events], total=total)


@router.get("/events/{event_id}", response_model=AlumniEventPublic)
async def get_event(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniEventService(db)
    event = await service.get_event(event_id, organization_id)
    return AlumniEventPublic.model_validate(event)


@router.patch("/events/{event_id}", response_model=AlumniEventPublic)
async def update_event(
    event_id: uuid.UUID,
    payload: AlumniEventUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniEventService(db)
    event = await service.update_event(
        event_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return AlumniEventPublic.model_validate(event)


@router.post("/events/{event_id}/status", response_model=AlumniEventPublic)
async def change_event_status(
    event_id: uuid.UUID,
    payload: AlumniEventStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniEventService(db)
    event = await service.change_status(event_id, organization_id, payload.status)
    return AlumniEventPublic.model_validate(event)


@router.delete("/events/{event_id}", response_model=MessageResponse)
async def delete_event(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AlumniEventService(db)
    await service.delete_event(event_id, organization_id)
    return MessageResponse(message="Alumni event deleted successfully.")


@router.get("/events/{event_id}/registrations", response_model=list[EventRegistrationPublic])
async def list_event_registrations(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.view")),
    db: AsyncSession = Depends(get_db),
):
    service = EventRegistrationService(db)
    registrations = await service.list_for_event(event_id, organization_id)
    return [EventRegistrationPublic.model_validate(r) for r in registrations]


@router.post("/registrations/{registration_id}/attendance", response_model=EventRegistrationPublic)
async def mark_registration_attendance(
    registration_id: uuid.UUID,
    payload: EventRegistrationAttendanceRequest,
    user: User = Depends(require_permissions("alumni.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EventRegistrationService(db)
    registration = await service.mark_attendance(registration_id, payload.status)
    return EventRegistrationPublic.model_validate(registration)


# ---- Staff: job referral moderation ----


@router.get("/referrals/all", response_model=JobReferralListResponse)
async def list_all_referrals(
    status_filter: ReferralStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("alumni.view")),
    db: AsyncSession = Depends(get_db),
):
    service = JobReferralService(db)
    referrals, total = await service.list_referrals(
        organization_id, status=status_filter, skip=skip, limit=limit
    )
    return JobReferralListResponse(
        items=[JobReferralPublic.model_validate(r) for r in referrals], total=total
    )
