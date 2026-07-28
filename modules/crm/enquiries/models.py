"""
CRM / Enquiries — ORM models.

An `Enquiry` captures a Lead's specific interest (which course, budget,
preferred timing). A single Lead can have multiple Enquiries over time
(e.g. interested in two different courses).
"""

import enum
import uuid

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.crm.leads.models import Lead  # noqa: F401


class EnquiryStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class Enquiry(TimestampedBase):
    __tablename__ = "crm_enquiries"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_interest: Mapped[str] = mapped_column(String(255), nullable=False)
    budget: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    preferred_batch_timing: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[EnquiryStatus] = mapped_column(
        SAEnum(
            EnquiryStatus,
            name="enquiry_status",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        default=EnquiryStatus.OPEN,
        server_default=EnquiryStatus.OPEN.value,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
