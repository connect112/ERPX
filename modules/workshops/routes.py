import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id
from modules.workshops.models import WorkshopStatus
from modules.workshops.schemas import (
    MarkAttendanceRequest,
    MessageResponse,
    WorkshopCreateRequest,
    WorkshopListResponse,
    WorkshopPublic,
    WorkshopRegistrationCreateRequest,
    WorkshopRegistrationPublic,
    WorkshopStatusChangeRequest,
    WorkshopUpdateRequest,
)
from modules.workshops.service import WorkshopRegistrationService, WorkshopService

router = APIRouter()


# ---- Student self-service ----


@router.get("/me", response_model=list[WorkshopPublic])
async def list_published_workshops(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopService(db)
    workshops, _total = await service.list_workshops(
        student.organization_id,
        status=WorkshopStatus.PUBLISHED,
        upcoming_only=True,
        skip=0,
        limit=200,
    )
    return [WorkshopPublic.model_validate(w) for w in workshops]


@router.get("/me/registrations", response_model=list[WorkshopRegistrationPublic])
async def list_my_registrations(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopRegistrationService(db)
    registrations = await service.list_for_student(student.id)
    return [WorkshopRegistrationPublic.model_validate(r) for r in registrations]


@router.post(
    "/{workshop_id}/register/me",
    response_model=WorkshopRegistrationPublic,
    status_code=status.HTTP_201_CREATED,
)
async def register_myself(
    workshop_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopRegistrationService(db)
    registration = await service.register(
        student.organization_id,
        workshop_id,
        contact_name=student.full_name,
        student_id=student.id,
        contact_email=student.email,
        contact_phone=student.phone,
    )
    return WorkshopRegistrationPublic.model_validate(registration)


# ---- Staff management ----


@router.post("", response_model=WorkshopPublic, status_code=status.HTTP_201_CREATED)
async def create_workshop(
    payload: WorkshopCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopService(db)
    workshop = await service.create_workshop(organization_id, **payload.model_dump())
    return WorkshopPublic.model_validate(workshop)


@router.get("", response_model=WorkshopListResponse)
async def list_workshops(
    status_filter: WorkshopStatus | None = Query(default=None, alias="status"),
    upcoming_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopService(db)
    workshops, total = await service.list_workshops(
        organization_id, status=status_filter, upcoming_only=upcoming_only, skip=skip, limit=limit
    )
    return WorkshopListResponse(items=[WorkshopPublic.model_validate(w) for w in workshops], total=total)


@router.get("/{workshop_id}", response_model=WorkshopPublic)
async def get_workshop(
    workshop_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopService(db)
    workshop = await service.get_workshop(workshop_id, organization_id)
    return WorkshopPublic.model_validate(workshop)


@router.patch("/{workshop_id}", response_model=WorkshopPublic)
async def update_workshop(
    workshop_id: uuid.UUID,
    payload: WorkshopUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopService(db)
    workshop = await service.update_workshop(
        workshop_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return WorkshopPublic.model_validate(workshop)


@router.post("/{workshop_id}/status", response_model=WorkshopPublic)
async def change_workshop_status(
    workshop_id: uuid.UUID,
    payload: WorkshopStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopService(db)
    workshop = await service.change_status(workshop_id, organization_id, payload.status)
    return WorkshopPublic.model_validate(workshop)


@router.delete("/{workshop_id}", response_model=MessageResponse)
async def delete_workshop(
    workshop_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopService(db)
    await service.delete_workshop(workshop_id, organization_id)
    return MessageResponse(message="Workshop deleted successfully.")


@router.post(
    "/{workshop_id}/registrations",
    response_model=WorkshopRegistrationPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_registration(
    workshop_id: uuid.UUID,
    payload: WorkshopRegistrationCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopRegistrationService(db)
    registration = await service.register(organization_id, workshop_id, **payload.model_dump())
    return WorkshopRegistrationPublic.model_validate(registration)


@router.get("/{workshop_id}/registrations", response_model=list[WorkshopRegistrationPublic])
async def list_registrations(
    workshop_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.view")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopRegistrationService(db)
    registrations = await service.list_for_workshop(workshop_id, organization_id)
    return [WorkshopRegistrationPublic.model_validate(r) for r in registrations]


@router.post("/registrations/{registration_id}/attendance", response_model=WorkshopRegistrationPublic)
async def mark_attendance(
    registration_id: uuid.UUID,
    payload: MarkAttendanceRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopRegistrationService(db)
    registration = await service.mark_attendance(registration_id, organization_id, payload.attended)
    return WorkshopRegistrationPublic.model_validate(registration)


@router.post("/registrations/{registration_id}/cancel", response_model=WorkshopRegistrationPublic)
async def cancel_registration(
    registration_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("workshops.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = WorkshopRegistrationService(db)
    registration = await service.cancel_registration(registration_id, organization_id)
    return WorkshopRegistrationPublic.model_validate(registration)
