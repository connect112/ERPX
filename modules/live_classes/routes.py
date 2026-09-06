import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.batches.repository import BatchEnrollmentRepository
from modules.live_classes.models import LiveClassStatus
from modules.live_classes.schemas import (
    LiveClassCreateRequest,
    LiveClassListResponse,
    LiveClassPublic,
    LiveClassStatusChangeRequest,
    LiveClassUpdateRequest,
    MessageResponse,
)
from modules.live_classes.service import LiveClassService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me", response_model=list[LiveClassPublic])
async def list_my_live_classes(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """The calling student's own live-class sessions (join link, recording),
    scoped to the batch(es) they belong to. Ownership-gated via
    `get_current_student`, no permission code."""
    batch_ids = await BatchEnrollmentRepository(db).list_batch_ids_for_student(
        student.id, student.organization_id
    )
    service = LiveClassService(db)
    entries = await service.list_for_batches(batch_ids, student.organization_id)
    return [LiveClassPublic.model_validate(e) for e in entries]


@router.post("", response_model=LiveClassPublic, status_code=status.HTTP_201_CREATED)
async def create_live_class(
    payload: LiveClassCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("live_classes.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LiveClassService(db)
    live_class = await service.create_live_class(organization_id, **payload.model_dump())
    return LiveClassPublic.model_validate(live_class)


@router.get("", response_model=LiveClassListResponse)
async def list_live_classes(
    batch_id: uuid.UUID | None = None,
    status_filter: LiveClassStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("live_classes.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LiveClassService(db)
    items, total = await service.list_live_classes(
        organization_id, batch_id=batch_id, status=status_filter, skip=skip, limit=limit
    )
    return LiveClassListResponse(items=[LiveClassPublic.model_validate(c) for c in items], total=total)


@router.get("/{live_class_id}", response_model=LiveClassPublic)
async def get_live_class(
    live_class_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("live_classes.view")),
    db: AsyncSession = Depends(get_db),
):
    service = LiveClassService(db)
    live_class = await service.get_live_class(live_class_id, organization_id)
    return LiveClassPublic.model_validate(live_class)


@router.patch("/{live_class_id}", response_model=LiveClassPublic)
async def update_live_class(
    live_class_id: uuid.UUID,
    payload: LiveClassUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("live_classes.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LiveClassService(db)
    live_class = await service.update_live_class(
        live_class_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return LiveClassPublic.model_validate(live_class)


@router.post("/{live_class_id}/status", response_model=LiveClassPublic)
async def change_live_class_status(
    live_class_id: uuid.UUID,
    payload: LiveClassStatusChangeRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("live_classes.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LiveClassService(db)
    live_class = await service.change_status(
        live_class_id, organization_id, payload.status, payload.recording_url
    )
    return LiveClassPublic.model_validate(live_class)


@router.delete("/{live_class_id}", response_model=MessageResponse)
async def delete_live_class(
    live_class_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("live_classes.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = LiveClassService(db)
    await service.delete_live_class(live_class_id, organization_id)
    return MessageResponse(message="Live class deleted successfully.")
