"""
Leave module — ORM models.

`LeaveType` configures an organization's leave policies (Casual, Sick,
Earned, ...). There is deliberately no stored "leave balance" table —
an employee's remaining balance for a leave type/year is computed live
in `service.py` as `annual_quota - sum(approved LeaveApplication days)`,
the same principle used throughout Accounting (Ledger balances, GST
returns) and Pentrix (Leaderboard): a balance that's derived can never
drift out of sync with the applications it's derived from.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.employees.models import Employee  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class LeaveApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class LeaveType(TimestampedBase):
    __tablename__ = "leave_types"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_leave_type_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    annual_quota: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    carry_forward_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_carry_forward_days: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LeaveApplication(TimestampedBase):
    __tablename__ = "leave_applications"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leave_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    number_of_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[LeaveApplicationStatus] = mapped_column(
        SAEnum(LeaveApplicationStatus, name="leave_application_status", values_callable=_values),
        default=LeaveApplicationStatus.PENDING,
        server_default=LeaveApplicationStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
