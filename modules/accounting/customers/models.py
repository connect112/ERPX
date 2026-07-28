"""
Accounting / Customers — ORM models.

`Customer` is the accounts-receivable master used by Invoices and
Receipts. It can stand alone (a walk-in / corporate customer with no
other record in the system) or optionally link back to a `Student` so a
student's course-fee invoices share the same customer record as their
LMS enrollment — set `student_id` when the customer *is* an enrolled
student rather than duplicating their contact details.
"""

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import SoftDeleteMixin, TimestampedBase
from modules.organizations.models import Organization  # noqa: F401
from modules.students.models import Student  # noqa: F401


class CustomerType(str, enum.Enum):
    INDIVIDUAL = "individual"
    STUDENT = "student"
    CORPORATE = "corporate"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Customer(TimestampedBase, SoftDeleteMixin):
    __tablename__ = "accounting_customers"
    __table_args__ = (
        UniqueConstraint("organization_id", "customer_code", name="uq_customer_org_code"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True
    )

    customer_code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_type: Mapped[CustomerType] = mapped_column(
        SAEnum(CustomerType, name="customer_type", values_callable=_values),
        default=CustomerType.INDIVIDUAL,
        server_default=CustomerType.INDIVIDUAL.value,
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)

    billing_address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    credit_limit: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
