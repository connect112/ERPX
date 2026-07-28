import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.timetable.schemas import (
    MessageResponse,
    TimetableEntryCreateRequest,
    TimetableEntryPublic,
    TimetableEntryUpdateRequest,
)
from modules.timetable.service import TimetableService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=TimetableEntryPublic, status_code=status.HTTP_201_CREATED)
async def create_timetable_entry(
    payload: TimetableEntryCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("timetable.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TimetableService(db)
    entry = await service.create_entry(organization_id, **payload.model_dump())
    return TimetableEntryPublic.model_validate(entry)


@router.get("", response_model=list[TimetableEntryPublic])
async def list_timetable_entries(
    batch_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("timetable.view")),
    db: AsyncSession = Depends(get_db),
):
    service = TimetableService(db)
    entries = await service.list_for_batch(batch_id, organization_id)
    return [TimetableEntryPublic.model_validate(e) for e in entries]


@router.get("/{entry_id}", response_model=TimetableEntryPublic)
async def get_timetable_entry(
    entry_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("timetable.view")),
    db: AsyncSession = Depends(get_db),
):
    service = TimetableService(db)
    entry = await service.get_entry(entry_id, organization_id)
    return TimetableEntryPublic.model_validate(entry)


@router.patch("/{entry_id}", response_model=TimetableEntryPublic)
async def update_timetable_entry(
    entry_id: uuid.UUID,
    payload: TimetableEntryUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("timetable.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TimetableService(db)
    entry = await service.update_entry(
        entry_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return TimetableEntryPublic.model_validate(entry)


@router.delete("/{entry_id}", response_model=MessageResponse)
async def delete_timetable_entry(
    entry_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("timetable.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = TimetableService(db)
    await service.delete_entry(entry_id, organization_id)
    return MessageResponse(message="Timetable entry deleted successfully.")
