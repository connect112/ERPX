import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.notifications.schemas import (
    BroadcastRequest,
    BroadcastResponse,
    MessageResponse,
    NotificationListResponse,
    NotificationPublic,
    UnreadCountResponse,
)
from modules.notifications.service import NotificationService
from modules.users.dependencies import get_current_user_organization_id

router = APIRouter()


@router.get("/me", response_model=NotificationListResponse)
async def list_my_notifications(
    unread_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    notifications, total = await service.list_for_user(
        user.id, unread_only=unread_only, skip=skip, limit=limit
    )
    return NotificationListResponse(
        items=[NotificationPublic.model_validate(n) for n in notifications], total=total
    )


@router.get("/me/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    count = await service.unread_count(user.id)
    return UnreadCountResponse(unread_count=count)


@router.post("/me/read-all", response_model=MessageResponse)
async def mark_all_read(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    count = await service.mark_all_read(user.id)
    return MessageResponse(message=f"Marked {count} notification(s) as read.")


@router.post("/me/{notification_id}/read", response_model=NotificationPublic)
async def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    notification = await service.mark_read(notification_id, user.id)
    return NotificationPublic.model_validate(notification)


@router.post("/broadcast", response_model=BroadcastResponse)
async def broadcast(
    payload: BroadcastRequest,
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    user: User = Depends(require_permissions("notifications.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    count = await service.broadcast_to_organization(
        organization_id,
        title=payload.title,
        body=payload.body,
        notification_type=payload.notification_type,
        link_url=payload.link_url,
    )
    return BroadcastResponse(notified_count=count)
