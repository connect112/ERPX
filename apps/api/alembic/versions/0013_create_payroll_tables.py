"""create payroll tables (salary components, structures, runs, payslips)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

salary_component_type_enum = postgresql.ENUM("earning", "deduction", name="salary_component_type")
payroll_run_status_enum = postgresql.ENUM("draft", "finalized", "paid", "cancelled", name="payroll_run_status")

_ALL_ENUMS = [salary_component_type_enum, payroll_run_status_enum]


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
    # `journal_source_module` (created in 0011) gains a value for payroll-sourced
    # postings. ALTER TYPE ... ADD VALUE cannot run inside the same transaction
    # as a later statement that uses the new value, but Alembic's per-migration
    # transaction boundary and the fact we don't use "payroll" until a later
    # migration/request make this safe on PostgreSQL 12+.
    op.execute("ALTER TYPE journal_source_module ADD VALUE IF NOT EXISTS 'payroll'")

    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    # ---- Salary Components ----
    op.create_table(
        "payroll_salary_components",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gl_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("component_type", postgresql.ENUM("earning", "deduction", name="salary_component_type", create_type=False), nullable=False),
        sa.Column("is_taxable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_salary_component_org_code"),
    )
    op.create_index("ix_payroll_salary_components_organization_id", "payroll_salary_components", ["organization_id"])

    # ---- Salary Structures & Lines ----
    op.create_table(
        "payroll_salary_structures",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("gross_monthly_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_deductions", sa.Numeric(14, 2), nullable=False),
        sa.Column("net_monthly_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_payroll_salary_structures_organization_id", "payroll_salary_structures", ["organization_id"])
    op.create_index("ix_payroll_salary_structures_employee_id", "payroll_salary_structures", ["employee_id"])
    op.create_index("ix_payroll_salary_structures_effective_from", "payroll_salary_structures", ["effective_from"])
    op.create_index("ix_payroll_salary_structures_is_active", "payroll_salary_structures", ["is_active"])

    op.create_table(
        "payroll_salary_structure_lines",
        *_tc(),
        sa.Column("salary_structure_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payroll_salary_structures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("salary_component_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payroll_salary_components.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_payroll_salary_structure_lines_salary_structure_id", "payroll_salary_structure_lines", ["salary_structure_id"])

    # ---- Payroll Runs ----
    op.create_table(
        "payroll_runs",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("net_payable_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_bank_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payment_journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("status", postgresql.ENUM("draft", "finalized", "paid", "cancelled", name="payroll_run_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("total_gross_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_deductions_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_net_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "period_year", "period_month", "branch_id", name="uq_payroll_run_period"),
    )
    op.create_index("ix_payroll_runs_organization_id", "payroll_runs", ["organization_id"])
    op.create_index("ix_payroll_runs_status", "payroll_runs", ["status"])

    # ---- Payslips & Lines ----
    op.create_table(
        "payroll_payslips",
        *_tc(),
        sa.Column("payroll_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("salary_structure_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payroll_salary_structures.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("days_in_month", sa.Integer(), nullable=False),
        sa.Column("paid_days", sa.Numeric(4, 1), nullable=False),
        sa.Column("lop_days", sa.Numeric(4, 1), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_deductions", sa.Numeric(14, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("payroll_run_id", "employee_id", name="uq_payslip_run_employee"),
    )
    op.create_index("ix_payroll_payslips_payroll_run_id", "payroll_payslips", ["payroll_run_id"])
    op.create_index("ix_payroll_payslips_employee_id", "payroll_payslips", ["employee_id"])

    op.create_table(
        "payroll_payslip_lines",
        *_tc(),
        sa.Column("payslip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payroll_payslips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("salary_component_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payroll_salary_components.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("component_type", postgresql.ENUM("earning", "deduction", name="salary_component_type", create_type=False), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_payroll_payslip_lines_payslip_id", "payroll_payslip_lines", ["payslip_id"])


def downgrade() -> None:
    op.drop_table("payroll_payslip_lines")
    op.drop_table("payroll_payslips")
    op.drop_table("payroll_runs")
    op.drop_table("payroll_salary_structure_lines")
    op.drop_table("payroll_salary_structures")
    op.drop_table("payroll_salary_components")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
    # Postgres does not support removing a value from an enum type; the
    # 'payroll' value added to journal_source_module is left in place.
