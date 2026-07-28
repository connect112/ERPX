"""
Accounting / TDS — ORM models.

`TDSSection` configures Indian Income Tax TDS sections (194J, 194C, ...)
and their rates. `TDSDeduction` is the actual deduction record created
when a vendor Payment withholds tax at source — it's the audit trail a
Form 26Q / Form 16A filing is built from, so unlike most reference data
here it is never deleted, only ever created.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.accounting.vendors.models import Vendor  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class TDSSection(TimestampedBase):
    __tablename__ = "accounting_tds_sections"
    __table_args__ = (
        UniqueConstraint("organization_id", "section_code", name="uq_tds_section_org_code"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_code: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    rate_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    threshold_amount: Mapped[float] = mapped_column(
        Numeric(14, 2), default=0, server_default="0", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TDSDeduction(TimestampedBase):
    __tablename__ = "accounting_tds_deductions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_vendors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tds_section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounting_tds_sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Opaque back-reference to the Payment this deduction was withheld on.
    payment_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    gross_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    tds_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    net_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    financial_year: Mapped[str] = mapped_column(String(9), nullable=False, index=True)  # e.g. "2026-2027"
    certificate_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deduction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
