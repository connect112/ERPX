"""
Assets module — ORM models.

Depreciation is *not* computed live the way stock levels or leave
balances are: once a period's depreciation is posted to the General
Ledger it's a permanent accounting fact, not a re-derivable aggregate —
the same reasoning Payroll stores `Payslip` rows instead of computing
pay live. `DepreciationRun` + `DepreciationEntry` mirror
`PayrollRun`/`Payslip` exactly: a run batches one entry per eligible
asset for a period, and finalizing it posts a single aggregate journal
entry via `JournalService`.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.accounting.journals.models import JournalEntry  # noqa: F401
from modules.accounting.ledger.models import Account  # noqa: F401
from modules.authentication.models import User  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.employees.models import Employee  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class DepreciationMethod(str, enum.Enum):
    STRAIGHT_LINE = "straight_line"
    DECLINING_BALANCE = "declining_balance"


class AssetStatus(str, enum.Enum):
    IN_USE = "in_use"
    IN_STORAGE = "in_storage"
    UNDER_MAINTENANCE = "under_maintenance"
    DISPOSED = "disposed"


class DepreciationRunStatus(str, enum.Enum):
    DRAFT = "draft"
    POSTED = "posted"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class AssetCategory(TimestampedBase):
    __tablename__ = "asset_categories"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_asset_category_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    default_useful_life_years: Mapped[int] = mapped_column(Integer, nullable=False)
    default_depreciation_method: Mapped[DepreciationMethod] = mapped_column(
        SAEnum(DepreciationMethod, name="depreciation_method", values_callable=_values),
        default=DepreciationMethod.STRAIGHT_LINE,
        server_default=DepreciationMethod.STRAIGHT_LINE.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Asset(TimestampedBase):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("organization_id", "asset_code", name="uq_asset_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("asset_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_to_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True
    )
    asset_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    accumulated_depreciation_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    depreciation_expense_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    disposal_journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True
    )

    asset_code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchase_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    salvage_value: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    useful_life_years: Mapped[int] = mapped_column(Integer, nullable=False)
    depreciation_method: Mapped[DepreciationMethod] = mapped_column(
        SAEnum(DepreciationMethod, name="depreciation_method", values_callable=_values),
        default=DepreciationMethod.STRAIGHT_LINE,
        server_default=DepreciationMethod.STRAIGHT_LINE.value,
        nullable=False,
    )
    status: Mapped[AssetStatus] = mapped_column(
        SAEnum(AssetStatus, name="asset_status", values_callable=_values),
        default=AssetStatus.IN_USE,
        server_default=AssetStatus.IN_USE.value,
        nullable=False,
        index=True,
    )
    disposal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposal_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DepreciationRun(TimestampedBase):
    __tablename__ = "asset_depreciation_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "period_year", "period_month", name="uq_depreciation_run_period"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_journal_entries.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[DepreciationRunStatus] = mapped_column(
        SAEnum(DepreciationRunStatus, name="depreciation_run_status", values_callable=_values),
        default=DepreciationRunStatus.DRAFT,
        server_default=DepreciationRunStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    total_depreciation_amount: Mapped[float] = mapped_column(
        Numeric(14, 2), default=0, server_default="0", nullable=False
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DepreciationEntry(TimestampedBase):
    __tablename__ = "asset_depreciation_entries"
    __table_args__ = (
        UniqueConstraint("asset_id", "depreciation_run_id", name="uq_depreciation_entry_asset_run"),
    )

    depreciation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asset_depreciation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depreciation_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    accumulated_depreciation: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    net_book_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
