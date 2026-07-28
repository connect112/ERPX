"""
Accounting / Vendors — ORM models.

`Vendor` is the accounts-payable master used by Expenses and Payments.
`pan_number` is captured here (rather than duplicated per-Expense/
Payment) because it's the vendor attribute TDS section applicability and
deduction rates hinge on.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import SoftDeleteMixin, TimestampedBase
from modules.organizations.models import Organization  # noqa: F401


class Vendor(TimestampedBase, SoftDeleteMixin):
    __tablename__ = "accounting_vendors"
    __table_args__ = (UniqueConstraint("organization_id", "vendor_code", name="uq_vendor_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    vendor_code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    pan_number: Mapped[str | None] = mapped_column(String(10), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    bank_account_number: Mapped[str | None] = mapped_column(String(34), nullable=True)
    bank_ifsc_code: Mapped[str | None] = mapped_column(String(11), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
