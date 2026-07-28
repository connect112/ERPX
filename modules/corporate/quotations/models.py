"""
Corporate / Quotations — ORM models.

A `Quotation` doesn't reference the `Contract` it may become — `Contract`
instead carries an optional `quotation_id` pointing back — so this
module has no dependency on `modules.corporate.contracts` at all.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_model import TimestampedBase
from modules.accounting.gst.models import GSTRate  # noqa: F401
from modules.corporate.clients.models import Client  # noqa: F401
from modules.corporate.projects.models import Project  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class QuotationStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Quotation(TimestampedBase):
    __tablename__ = "corporate_quotations"
    __table_args__ = (
        UniqueConstraint("organization_id", "quotation_number", name="uq_quotation_org_number"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("corporate_projects.id", ondelete="SET NULL"), nullable=True
    )

    quotation_number: Mapped[str] = mapped_column(String(50), nullable=False)
    quotation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[QuotationStatus] = mapped_column(
        SAEnum(QuotationStatus, name="quotation_status", values_callable=_values),
        default=QuotationStatus.DRAFT,
        server_default=QuotationStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    subtotal_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )


class QuotationLine(TimestampedBase):
    __tablename__ = "corporate_quotation_lines"

    quotation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_quotations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gst_rate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_gst_rates.id", ondelete="SET NULL"), nullable=True
    )

    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), default=1, server_default="1", nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    line_subtotal: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    quotation: Mapped["Quotation"] = relationship(back_populates="lines")
