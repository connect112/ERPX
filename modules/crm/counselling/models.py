"""
CRM / Counselling — ORM models.

A `CounsellingSession` records a scheduled or completed counselling
interaction for a Lead, including the assigned counsellor and any
course recommendation, feeding into the eventual Admission decision.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.crm.leads.models import Lead  # noqa: F401


class CounsellingMode(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    PHONE = "phone"


class CounsellingStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class CounsellingSession(TimestampedBase):
    __tablename__ = "crm_counselling_sessions"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    counselor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    mode: Mapped[CounsellingMode] = mapped_column(
        SAEnum(CounsellingMode, name="counselling_mode", values_callable=_values),
        default=CounsellingMode.PHONE,
        server_default=CounsellingMode.PHONE.value,
        nullable=False,
    )
    status: Mapped[CounsellingStatus] = mapped_column(
        SAEnum(CounsellingStatus, name="counselling_status", values_callable=_values),
        default=CounsellingStatus.SCHEDULED,
        server_default=CounsellingStatus.SCHEDULED.value,
        nullable=False,
    )

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recommended_course: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
