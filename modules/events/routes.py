import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.events.models import EventType
from modules.events.schemas import (
    EventCreateRequest,
    EventListResponse,
    EventPublic,
    EventUpdateRequest,
    MessageResponse,
)
from modules.events.service import EventService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("", response_model=EventListResponse)
async def list_events(
    event_type: EventType | None = Query(default=None),
    starts_after: datetime | None = Query(default=None),
    starts_before: datetime | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = EventService(db)
    events, total = await service.list_events(
        organization_id,
        event_type=event_type,
        starts_after=starts_after,
        starts_before=starts_before,
        skip=skip,
        limit=limit,
    )
    return EventListResponse(items=[EventPublic.model_validate(e) for e in events], total=total)


@router.get("/{event_id}", response_model=EventPublic)
async def get_event(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = EventService(db)
    event = await service.get_event(event_id, organization_id)
    return EventPublic.model_validate(event)


@router.post("", response_model=EventPublic, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("events.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EventService(db)
    event = await service.create_event(organization_id, user.id, **payload.model_dump())
    return EventPublic.model_validate(event)


@router.patch("/{event_id}", response_model=EventPublic)
async def update_event(
    event_id: uuid.UUID,
    payload: EventUpdateRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("events.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EventService(db)
    event = await service.update_event(
        event_id, organization_id, **payload.model_dump(exclude_unset=True)
    )
    return EventPublic.model_validate(event)


@router.delete("/{event_id}", response_model=MessageResponse)
async def delete_event(
    event_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("events.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = EventService(db)
    await service.delete_event(event_id, organization_id)
    return MessageResponse(message="Event deleted successfully.")
