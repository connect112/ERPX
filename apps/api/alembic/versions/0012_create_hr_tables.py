"""create hr tables (departments, designations, employees, attendance, leave)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

employment_type_enum = postgresql.ENUM(
    "full_time", "part_time", "contract", "intern", "consultant", name="employment_type"
)
employment_status_enum = postgresql.ENUM(
    "active", "on_leave", "suspended", "resigned", "terminated", "retired", name="employment_status"
)
attendance_status_enum = postgresql.ENUM(
    "present", "absent", "half_day", "on_leave", "holiday", "week_off", name="attendance_status"
)
leave_application_status_enum = postgresql.ENUM(
    "pending", "approved", "rejected", "cancelled", name="leave_application_status"
)

_ALL_ENUMS = [
    employment_type_enum,
    employment_status_enum,
    attendance_status_enum,
    leave_application_status_enum,
]


def _tc():
    return [
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    # ---- Departments (head_employee_id FK added after `employees` exists) ----
    op.create_table(
        "hr_departments",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hr_departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("head_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_department_org_code"),
    )
    op.create_index("ix_hr_departments_organization_id", "hr_departments", ["organization_id"])

    # ---- Designations ----
    op.create_table(
        "hr_designations",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("grade_level", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_designation_org_code"),
    )
    op.create_index("ix_hr_designations_organization_id", "hr_designations", ["organization_id"])

    # ---- Employees ----
    op.create_table(
        "employees",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hr_departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("designation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hr_designations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reporting_manager_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("employee_code", sa.String(length=30), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("gender", postgresql.ENUM("male", "female", "other", "prefer_not_to_say", name="gender", create_type=False), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("emergency_contact_name", sa.String(length=255), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(length=32), nullable=True),
        sa.Column("employment_type", postgresql.ENUM("full_time", "part_time", "contract", "intern", "consultant", name="employment_type", create_type=False), nullable=False, server_default="full_time"),
        sa.Column("employment_status", postgresql.ENUM("active", "on_leave", "suspended", "resigned", "terminated", "retired", name="employment_status", create_type=False), nullable=False, server_default="active"),
        sa.Column("date_of_joining", sa.Date(), nullable=False),
        sa.Column("date_of_exit", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "employee_code", name="uq_employee_org_code"),
    )
    op.create_index("ix_employees_organization_id", "employees", ["organization_id"])
    op.create_index("ix_employees_branch_id", "employees", ["branch_id"])
    op.create_index("ix_employees_department_id", "employees", ["department_id"])
    op.create_index("ix_employees_designation_id", "employees", ["designation_id"])
    op.create_index("ix_employees_reporting_manager_id", "employees", ["reporting_manager_id"])
    op.create_index("ix_employees_employment_status", "employees", ["employment_status"])

    # `hr_departments.head_employee_id` can only reference `employees` now that it exists.
    op.create_foreign_key(
        "fk_department_head_employee", "hr_departments", "employees", ["head_employee_id"], ["id"], ondelete="SET NULL"
    )

    # ---- Attendance ----
    op.create_table(
        "attendance_records",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("work_hours", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", postgresql.ENUM("present", "absent", "half_day", "on_leave", "holiday", "week_off", name="attendance_status", create_type=False), nullable=False, server_default="present"),
        sa.Column("is_regularized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("regularization_reason", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.UniqueConstraint("employee_id", "attendance_date", name="uq_attendance_employee_date"),
    )
    op.create_index("ix_attendance_records_organization_id", "attendance_records", ["organization_id"])
    op.create_index("ix_attendance_records_employee_id", "attendance_records", ["employee_id"])
    op.create_index("ix_attendance_records_attendance_date", "attendance_records", ["attendance_date"])
    op.create_index("ix_attendance_records_status", "attendance_records", ["status"])

    # ---- Leave ----
    op.create_table(
        "leave_types",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("annual_quota", sa.Numeric(5, 1), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("carry_forward_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_carry_forward_days", sa.Numeric(5, 1), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_leave_type_org_code"),
    )
    op.create_index("ix_leave_types_organization_id", "leave_types", ["organization_id"])

    op.create_table(
        "leave_applications",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leave_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("number_of_days", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "approved", "rejected", "cancelled", name="leave_application_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_leave_applications_organization_id", "leave_applications", ["organization_id"])
    op.create_index("ix_leave_applications_employee_id", "leave_applications", ["employee_id"])
    op.create_index("ix_leave_applications_leave_type_id", "leave_applications", ["leave_type_id"])
    op.create_index("ix_leave_applications_start_date", "leave_applications", ["start_date"])
    op.create_index("ix_leave_applications_end_date", "leave_applications", ["end_date"])
    op.create_index("ix_leave_applications_status", "leave_applications", ["status"])


def downgrade() -> None:
    op.drop_table("leave_applications")
    op.drop_table("leave_types")
    op.drop_table("attendance_records")
    op.drop_constraint("fk_department_head_employee", "hr_departments", type_="foreignkey")
    op.drop_table("employees")
    op.drop_table("hr_designations")
    op.drop_table("hr_departments")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
