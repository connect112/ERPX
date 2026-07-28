"""
Marketing / Referrals — ORM models.

`ReferralProgram` configures reward amounts; `Referral` is one
referrer-to-referee submission against a program. Actual reward payout
is a manual Accounting Expense the finance team records referencing
this `Referral` — this module only tracks that a reward was earned and
its amount, not the cash movement itself (same boundary Procurement
draws around converting a received PO into a payable Expense).
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.crm.leads.models import Lead  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401
from modules.students.models import Student  # noqa: F401


class ReferralStatus(str, enum.Enum):
    PENDING = "pending"
    CONVERTED = "converted"
    REWARDED = "rewarded"
    EXPIRED = "expired"
    REJECTED = "rejected"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class ReferralProgram(TimestampedBase):
    __tablename__ = "marketing_referral_programs"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_referral_program_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    referrer_reward_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    referee_discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    max_referrals_per_referrer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Referral(TimestampedBase):
    __tablename__ = "marketing_referrals"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referral_program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("marketing_referral_programs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    referrer_student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )
    converted_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("crm_leads.id", ondelete="SET NULL"), nullable=True
    )

    referee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    referee_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    referee_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[ReferralStatus] = mapped_column(
        SAEnum(ReferralStatus, name="referral_status", values_callable=_values),
        default=ReferralStatus.PENDING,
        server_default=ReferralStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    reward_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
