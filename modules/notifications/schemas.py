import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from modules.notifications.models import NotificationType


class NotificationPublic(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    body: str | None
    notification_type: NotificationType
    link_url: str | None
    source: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationPublic]
    total: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class BroadcastRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str | None = None
    notification_type: NotificationType = NotificationType.INFO
    link_url: str | None = None


class BroadcastResponse(BaseModel):
    notified_count: int


class MessageResponse(BaseModel):
    message: str
