"""
Communication module — audit log for outbound email/SMS/WhatsApp.

`CommunicationService.send_and_log()` is a real send: it calls the same
`packages.email`, `packages.sms`, `packages.whatsapp` clients every other
module already uses, then records what happened (recipient, channel,
status, error if any) so there's a single place to see everything the
platform has sent to someone — independent of which module triggered it.
`CommunicationService.record()` is the generic write path other modules
can call after their own send (e.g. Celery tasks that already dispatch
via those same clients) without going through this module's own send
endpoint.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class CommunicationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class CommunicationStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class CommunicationLog(TimestampedBase):
    __tablename__ = "communication_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[CommunicationChannel] = mapped_column(
        SAEnum(CommunicationChannel, name="communication_channel", values_callable=_values),
        nullable=False,
        index=True,
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[CommunicationStatus] = mapped_column(
        SAEnum(CommunicationStatus, name="communication_status", values_callable=_values),
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    sent_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
