"""
Notifications module — in-app notification center.

`NotificationService.create_notification()` (and `broadcast_to_organization`)
are the generic, reusable entry points any other module can call when it
wants to put something in a user's notification tray — an assignment
graded, a ticket replied to, an approval request waiting on them. This
module doesn't know or care who calls it, mirroring how `modules.documents`
and `modules.workflow` are generic services other modules plug into rather
than reaching into. It's deliberately separate from SMS/WhatsApp/email
(those are external delivery channels each triggering module already
owns) — this is the in-app inbox.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class NotificationType(str, enum.Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    ACTION_REQUIRED = "action_required"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Notification(TimestampedBase):
    __tablename__ = "notifications"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notification_type", values_callable=_values),
        default=NotificationType.INFO,
        server_default=NotificationType.INFO.value,
        nullable=False,
    )
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
