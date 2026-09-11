"""
HR module — ORM models.

`Department` and `Designation` are the organizational-structure masters
`Employee.department_id`/`designation_id` reference. `head_employee_id`
points at `employees.id` by table name only (no model import) — the
same one-directional-dependency approach `modules.employees` uses in
reverse, so neither module needs to import the other's classes.
"""

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.organizations.models import Organization  # noqa: F401


class Department(TimestampedBase):
    __tablename__ = "hr_departments"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_department_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("hr_departments.id", ondelete="SET NULL"), nullable=True
    )
    head_employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Designation(TimestampedBase):
    __tablename__ = "hr_designations"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_designation_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    grade_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # What EmployeeService.invite_employee grants beyond the basic
    # employee-portal login, for any employee holding this designation —
    # see migration 0041 for the full rationale. Both optional: most
    # designations (Accountant, HR Executive, ...) grant neither, and
    # every employee gets the basic self-service portal regardless of
    # designation, or lack of one.
    linked_role_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )
    grants_trainer_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
