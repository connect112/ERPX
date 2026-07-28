"""
Attendance module — ORM models.

One `AttendanceRecord` per employee per calendar day. Check-in/check-out
punches update the same row rather than appending separate punch rows —
a day's attendance is a single fact (present/absent/half-day + hours
worked), not a log of raw events, which keeps every downstream read
(monthly summaries, payroll inputs) a simple aggregate over one row per
day instead of a punch-pairing exercise.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.branches.models import Branch  # noqa: F401
from modules.employees.models import Employee  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    HALF_DAY = "half_day"
    ON_LEAVE = "on_leave"
    HOLIDAY = "holiday"
    WEEK_OFF = "week_off"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class AttendanceRecord(TimestampedBase):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("employee_id", "attendance_date", name="uq_attendance_employee_date"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    attendance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    check_in_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    work_hours: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    status: Mapped[AttendanceStatus] = mapped_column(
        SAEnum(AttendanceStatus, name="attendance_status", values_callable=_values),
        default=AttendanceStatus.PRESENT,
        server_default=AttendanceStatus.PRESENT.value,
        nullable=False,
        index=True,
    )
    is_regularized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    regularization_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
