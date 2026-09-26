"""
Expense claims module — ORM models.

An employee's reimbursement claim (a receipt, description, and amount),
distinct from `modules.accounting.expenses.Expense` (a vendor bill going
through its own maker-checker AP workflow — unrelated concept, same
English word). An approved claim gets applied as a one-off PayslipLine
onto that employee's payslip for the period it was submitted in, via
the existing PayrollService.add_payslip_line -- see
modules/payroll/service.py.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.documents.models import Document  # noqa: F401
from modules.employees.models import Employee  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401
from modules.payroll.models import PayrollRun  # noqa: F401


class ExpenseClaimStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class ExpenseClaim(TimestampedBase):
    __tablename__ = "expense_claims"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    receipt_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Which month's payslip this claim applies to -- defaults to the
    # submission month (see service.py's submit_claim), so payroll's
    # generate_run knows which period's employees to scan for newly
    # approved claims to add as a line.
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    # Set once generate_run actually adds this claim as a payslip line, so
    # a later regenerate of the same run doesn't add it twice. ON DELETE
    # SET NULL: if that run is later cancelled+deleted, this claim
    # automatically becomes available to apply again on the next generate,
    # with no extra bookkeeping needed here.
    applied_payroll_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="SET NULL"), nullable=True
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    status: Mapped[ExpenseClaimStatus] = mapped_column(
        SAEnum(ExpenseClaimStatus, name="expense_claim_status", values_callable=_values),
        default=ExpenseClaimStatus.PENDING,
        server_default=ExpenseClaimStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
