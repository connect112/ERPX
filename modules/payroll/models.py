"""
Payroll module — ORM models.

Flow: `SalaryComponent` (org-wide master, each tied to a GL account) is
assembled into a per-employee `SalaryStructure` (versioned by
`effective_from`/`effective_to` — a revision creates a new row rather
than mutating the old one, preserving history for past payslips). A
`PayrollRun` generates one `Payslip` per active employee for a month,
snapshotting `PayslipLine` amounts from the structure at generation time
(prorated for LOP via Attendance) so a later structure change never
alters an already-generated payslip. Finalizing a run is the only place
Payroll touches the General Ledger, via `JournalService.post_transaction`
— it never writes `JournalEntry`/`JournalLine` directly, the same rule
every Accounting sub-module follows.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_model import TimestampedBase
from modules.accounting.bank.models import BankAccount  # noqa: F401
from modules.accounting.journals.models import JournalEntry  # noqa: F401
from modules.accounting.ledger.models import Account  # noqa: F401
from modules.authentication.models import User  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.employees.models import Employee  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class SalaryComponentType(str, enum.Enum):
    EARNING = "earning"
    DEDUCTION = "deduction"


class PayrollRunStatus(str, enum.Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    PAID = "paid"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class SalaryComponent(TimestampedBase):
    __tablename__ = "payroll_salary_components"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_salary_component_org_code"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gl_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    component_type: Mapped[SalaryComponentType] = mapped_column(
        SAEnum(SalaryComponentType, name="salary_component_type", values_callable=_values), nullable=False
    )
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SalaryStructure(TimestampedBase):
    __tablename__ = "payroll_salary_structures"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )

    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    gross_monthly_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    total_deductions: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    net_monthly_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list["SalaryStructureLine"]] = relationship(
        back_populates="structure", cascade="all, delete-orphan"
    )


class SalaryStructureLine(TimestampedBase):
    __tablename__ = "payroll_salary_structure_lines"

    salary_structure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_salary_structures.id", ondelete="CASCADE"), nullable=False, index=True
    )
    salary_component_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_salary_components.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    structure: Mapped["SalaryStructure"] = relationship(back_populates="lines")


class PayrollRun(TimestampedBase):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "period_year", "period_month", "branch_id", name="uq_payroll_run_period"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    net_payable_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=True
    )
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_bank_accounts.id", ondelete="SET NULL"), nullable=True
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True
    )
    payment_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PayrollRunStatus] = mapped_column(
        SAEnum(PayrollRunStatus, name="payroll_run_status", values_callable=_values),
        default=PayrollRunStatus.DRAFT,
        server_default=PayrollRunStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    total_gross_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    total_deductions_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    total_net_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Payslip(TimestampedBase):
    __tablename__ = "payroll_payslips"
    __table_args__ = (
        UniqueConstraint("payroll_run_id", "employee_id", name="uq_payslip_run_employee"),
    )

    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    salary_structure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_salary_structures.id", ondelete="RESTRICT"), nullable=False
    )

    days_in_month: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_days: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    lop_days: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)
    gross_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    total_deductions: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    net_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    lines: Mapped[list["PayslipLine"]] = relationship(back_populates="payslip", cascade="all, delete-orphan")


class PayslipLine(TimestampedBase):
    __tablename__ = "payroll_payslip_lines"

    payslip_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_payslips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    salary_component_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_salary_components.id", ondelete="RESTRICT"), nullable=False
    )
    component_type: Mapped[SalaryComponentType] = mapped_column(
        SAEnum(SalaryComponentType, name="salary_component_type", values_callable=_values), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    payslip: Mapped["Payslip"] = relationship(back_populates="lines")
