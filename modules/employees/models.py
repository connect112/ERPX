"""
Employees module — ORM models.

`Employee` is the HR master record, analogous to how `Student` anchors
the LMS side: organization/branch scoped, optionally linked to a `User`
login account via a nullable `user_id` provisioned later. Department and
Designation are referenced by table name only (no model import) to avoid
a circular import with `modules.hr`, which itself has no reason to
import `Employee`.
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
from modules.organizations.models import Organization  # noqa: F401
from modules.users.models import Gender  # noqa: F401


class EmploymentType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERN = "intern"
    CONSULTANT = "consultant"


class EmploymentStatus(str, enum.Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    RESIGNED = "resigned"
    TERMINATED = "terminated"
    RETIRED = "retired"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Employee(TimestampedBase, SoftDeleteMixin):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("organization_id", "employee_code", name="uq_employee_org_code"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hr_departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    designation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hr_designations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reporting_manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )

    employee_code: Mapped[str] = mapped_column(String(30), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gender: Mapped[Gender | None] = mapped_column(
        SAEnum(Gender, name="gender", values_callable=_values), nullable=True
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    emergency_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    employment_type: Mapped[EmploymentType] = mapped_column(
        SAEnum(EmploymentType, name="employment_type", values_callable=_values),
        default=EmploymentType.FULL_TIME,
        server_default=EmploymentType.FULL_TIME.value,
        nullable=False,
    )
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        SAEnum(EmploymentStatus, name="employment_status", values_callable=_values),
        default=EmploymentStatus.ACTIVE,
        server_default=EmploymentStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )
    date_of_joining: Mapped[date] = mapped_column(Date, nullable=False)
    date_of_exit: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
