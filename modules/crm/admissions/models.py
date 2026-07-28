"""
CRM / Admissions — ORM models.

An `Admission` is the terminal outcome of a Lead's journey through the
CRM pipeline: course, batch, and fee details once a Lead converts.
Creating an Admission also flips the parent Lead to CONVERTED (handled
in the service layer, not here). The Students module (built next) will
create the actual Student record from a confirmed Admission.
"""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.crm.leads.models import Lead  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class AdmissionStatus(str, enum.Enum):
    ON_HOLD = "on_hold"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Admission(TimestampedBase):
    __tablename__ = "crm_admissions"

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crm_leads.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    fee_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)
    admission_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[AdmissionStatus] = mapped_column(
        SAEnum(
            AdmissionStatus,
            name="admission_status",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        default=AdmissionStatus.ON_HOLD,
        server_default=AdmissionStatus.ON_HOLD.value,
        nullable=False,
    )
