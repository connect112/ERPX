"""
Students module — ORM models.

A `Student` is created either directly (manual enrollment) or via
`POST /students/from-admission/{admission_id}` once a CRM Admission is
CONFIRMED — that endpoint copies course/batch details across and links
back to the Admission so the CRM-to-Student handoff is traceable.
`user_id` is nullable and populated later when a student portal login
account is provisioned (Authentication module), keeping enrollment
records independent of login/account state.
"""

import enum
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import SoftDeleteMixin, TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.crm.admissions.models import Admission  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401
from modules.users.models import Gender  # noqa: F401


class StudentStatus(str, enum.Enum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    DROPPED = "dropped"
    TRANSFERRED = "transferred"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Student(TimestampedBase, SoftDeleteMixin):
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("organization_id", "student_code", name="uq_student_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    admission_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("crm_admissions.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )

    student_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    gender: Mapped[Gender | None] = mapped_column(
        SAEnum(Gender, name="gender", values_callable=_values),
        nullable=True,
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    guardian_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    course_name: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    enrollment_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[StudentStatus] = mapped_column(
        SAEnum(StudentStatus, name="student_status", values_callable=_values),
        default=StudentStatus.ACTIVE,
        server_default=StudentStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
