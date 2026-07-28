"""
CRM / Follow-ups — ORM models.

A `FollowUp` is a scheduled or completed interaction (call, email,
meeting) against a Lead, letting counsellors track outreach history and
plan next touchpoints.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.crm.leads.models import Lead  # noqa: F401


class FollowUpType(str, enum.Enum):
    CALL = "call"
    EMAIL = "email"
    MEETING = "meeting"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    OTHER = "other"


class FollowUpStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    MISSED = "missed"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class FollowUp(TimestampedBase):
    __tablename__ = "crm_followups"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    follow_up_type: Mapped[FollowUpType] = mapped_column(
        SAEnum(FollowUpType, name="followup_type", values_callable=_values),
        default=FollowUpType.CALL,
        server_default=FollowUpType.CALL.value,
        nullable=False,
    )
    status: Mapped[FollowUpStatus] = mapped_column(
        SAEnum(FollowUpStatus, name="followup_status", values_callable=_values),
        default=FollowUpStatus.SCHEDULED,
        server_default=FollowUpStatus.SCHEDULED.value,
        nullable=False,
    )

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
