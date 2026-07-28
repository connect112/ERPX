import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.accounting.journals.models import JournalEntryStatus, JournalSourceModule
from modules.accounting.journals.schemas import (
    JournalEntryCreateRequest,
    JournalEntryPublic,
    MessageResponse,
)
from modules.accounting.journals.service import JournalService
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.post("", response_model=JournalEntryPublic, status_code=status.HTTP_201_CREATED)
async def create_manual_journal_entry(
    payload: JournalEntryCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.journals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = JournalService(db)
    entry = await service.create_manual_draft(
        organization_id,
        entry_date=payload.entry_date,
        memo=payload.memo,
        branch_id=payload.branch_id,
        lines=[line.model_dump() for line in payload.lines],
        created_by_user_id=user.id,
    )
    return JournalEntryPublic.model_validate(entry)


@router.get("", response_model=dict)
async def list_journal_entries(
    status_filter: JournalEntryStatus | None = Query(default=None, alias="status"),
    source_module: JournalSourceModule | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.journals.view")),
    db: AsyncSession = Depends(get_db),
):
    service = JournalService(db)
    entries, total = await service.list_entries(
        organization_id,
        status=status_filter,
        source_module=source_module,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [JournalEntryPublic.model_validate(e) for e in entries],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{entry_id}", response_model=JournalEntryPublic)
async def get_journal_entry(
    entry_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.journals.view")),
    db: AsyncSession = Depends(get_db),
):
    service = JournalService(db)
    entry = await service.get_entry(entry_id, organization_id)
    return JournalEntryPublic.model_validate(entry)


@router.post("/{entry_id}/post", response_model=JournalEntryPublic)
async def post_journal_entry(
    entry_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.journals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = JournalService(db)
    entry = await service.post_draft_entry(entry_id, organization_id)
    return JournalEntryPublic.model_validate(entry)


@router.post("/{entry_id}/reverse", response_model=JournalEntryPublic)
async def reverse_journal_entry(
    entry_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("accounting.journals.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = JournalService(db)
    reversal = await service.reverse_entry(entry_id, organization_id)
    return JournalEntryPublic.model_validate(reversal)
