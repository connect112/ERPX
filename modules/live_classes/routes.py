import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.batches.repository import BatchEnrollmentRepository, BatchRepository
from modules.live_classes.jitsi import build_room_name, jitsi_domain, jitsi_enabled, mint_join_token
from modules.live_classes.models import LiveClassStatus
from modules.live_classes.schemas import (
    LiveClassCreateRequest,
    LiveClassJoinToken,
    LiveClassListResponse,
    LiveClassPublic,
    LiveClassStatusChangeRequest,
    LiveClassUpdateRequest,
    MessageResponse,
)
from modules.live_classes.service import LiveClassService
from modules.students.dependencies import get_current_student
from modules.students.models import Student
from modules.trainers.dependencies import get_current_trainer
from modules.trainers.models import Trainer
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()

# A join token is only meaningful while the class hasn't wrapped up —
# minting one for a completed/cancelled class would just hand out access
# to an empty room nobody has a reason to be in.
_JOINABLE_STATUSES = {LiveClassStatus.SCHEDULED, LiveClassStatus.LIVE}


def _require_jitsi_configured() -> None:
    if not jitsi_enabled():
        raise ValidationError("Self-hosted video calling isn't configured for this environment.")


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


@router.post("/{live_class_id}/join-token", response_model=LiveClassJoinToken)
async def get_live_class_join_token_as_student(
    live_class_id: uuid.UUID,
    student: Student = Depends(get_current_student),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mints a short-lived Jitsi JWT for the calling student to join this
    live class's embedded call — never as moderator. Ownership-gated: the
    class must belong to a batch this student is actually enrolled in,
    same 404-not-403 reasoning as everywhere else in this file."""
    _require_jitsi_configured()
    service = LiveClassService(db)
    batch_ids = await BatchEnrollmentRepository(db).list_batch_ids_for_student(
        student.id, student.organization_id
    )
    live_class = await service.get_live_class(live_class_id, student.organization_id)
    if live_class.batch_id not in batch_ids:
        raise NotFoundError("Live class", live_class_id)
    if live_class.status not in _JOINABLE_STATUSES:
        raise ValidationError("This live class isn't currently joinable.")

    token = mint_join_token(live_class_id, user.id, user.full_name, user.email, moderator=False)
    return LiveClassJoinToken(domain=jitsi_domain(), room=build_room_name(live_class_id), jwt=token)


@router.get("/trainer/me", response_model=list[LiveClassPublic])
async def list_my_live_classes_as_trainer(
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    """The calling trainer's own live-class sessions, scoped to the
    batch(es) they teach. Ownership-gated via `get_current_trainer`, no
    permission code — mirrors list_my_live_classes' student version above
    and modules/batches/routes.py's own /me for trainers."""
    batches = await BatchRepository(db).list_for_trainer(trainer.id, trainer.organization_id)
    batch_ids = [b.id for b in batches]
    service = LiveClassService(db)
    entries = await service.list_for_batches(batch_ids, trainer.organization_id)
    return [LiveClassPublic.model_validate(e) for e in entries]


@router.post("/trainer/{live_class_id}/status", response_model=LiveClassPublic)
async def change_live_class_status_as_trainer(
    live_class_id: uuid.UUID,
    payload: LiveClassStatusChangeRequest,
    trainer: Trainer = Depends(get_current_trainer),
    db: AsyncSession = Depends(get_db),
):
    """Same status machine as the admin /{live_class_id}/status endpoint
    below, but ownership-gated instead of permission-gated: a trainer may
    start/complete/cancel a live class only for a batch they actually
    teach. 404 (not 403) on a class outside that set, same reasoning as
    every other ownership check in this codebase — don't confirm the
    class exists to someone who has no business knowing that."""
    service = LiveClassService(db)
    batches = await BatchRepository(db).list_for_trainer(trainer.id, trainer.organization_id)
    batch_ids = {b.id for b in batches}

    live_class = await service.get_live_class(live_class_id, trainer.organization_id)
    if live_class.batch_id not in batch_ids:
        raise NotFoundError("Live class", live_class_id)

    updated = await service.change_status(
        live_class_id, trainer.organization_id, payload.status, payload.recording_url
    )
    return LiveClassPublic.model_validate(updated)


@router.post("/trainer/{live_class_id}/join-token", response_model=LiveClassJoinToken)
async def get_live_class_join_token_as_trainer(
    live_class_id: uuid.UUID,
    trainer: Trainer = Depends(get_current_trainer),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Mints a short-lived Jitsi JWT for the calling trainer to join this
    live class's embedded call, as moderator. Ownership-gated: the class
    must belong to a batch this trainer actually teaches."""
    _require_jitsi_configured()
    service = LiveClassService(db)
    batches = await BatchRepository(db).list_for_trainer(trainer.id, trainer.organization_id)
    batch_ids = {b.id for b in batches}

    live_class = await service.get_live_class(live_class_id, trainer.organization_id)
    if live_class.batch_id not in batch_ids:
        raise NotFoundError("Live class", live_class_id)
    if live_class.status not in _JOINABLE_STATUSES:
        raise ValidationError("This live class isn't currently joinable.")

    token = mint_join_token(live_class_id, user.id, user.full_name, user.email, moderator=True)
    return LiveClassJoinToken(domain=jitsi_domain(), room=build_room_name(live_class_id), jwt=token)


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
