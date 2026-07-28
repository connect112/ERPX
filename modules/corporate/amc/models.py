"""
Corporate / AMC — ORM models.

`AMCContract` is a specialized view of an Annual Maintenance Contract —
it optionally links back to the generic `Contract` that formalizes it
(for value/signature tracking) while owning AMC-specific fields
(coverage, billing frequency, renewal reminder window) that don't belong
on the generic `Contract` record.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_model import TimestampedBase
from modules.corporate.clients.models import Client  # noqa: F401
from modules.corporate.contracts.models import Contract  # noqa: F401
from modules.employees.models import Employee  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class BillingFrequency(str, enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class AMCStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    RENEWED = "renewed"
    CANCELLED = "cancelled"


class AMCVisitStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class AMCContract(TimestampedBase):
    __tablename__ = "corporate_amc_contracts"
    __table_args__ = (UniqueConstraint("organization_id", "amc_number", name="uq_amc_contract_org_number"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("corporate_contracts.id", ondelete="SET NULL"), nullable=True
    )

    amc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    coverage_description: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    renewal_reminder_days: Mapped[int] = mapped_column(Integer, default=30, server_default="30", nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    billing_frequency: Mapped[BillingFrequency] = mapped_column(
        SAEnum(BillingFrequency, name="amc_billing_frequency", values_callable=_values), nullable=False
    )
    status: Mapped[AMCStatus] = mapped_column(
        SAEnum(AMCStatus, name="amc_status", values_callable=_values),
        default=AMCStatus.ACTIVE,
        server_default=AMCStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )

    visits: Mapped[list["AMCVisit"]] = relationship(back_populates="amc_contract", cascade="all, delete-orphan")


class AMCVisit(TimestampedBase):
    __tablename__ = "corporate_amc_visits"

    amc_contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("corporate_amc_contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    engineer_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )

    visit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AMCVisitStatus] = mapped_column(
        SAEnum(AMCVisitStatus, name="amc_visit_status", values_callable=_values),
        default=AMCVisitStatus.SCHEDULED,
        server_default=AMCVisitStatus.SCHEDULED.value,
        nullable=False,
        index=True,
    )

    amc_contract: Mapped["AMCContract"] = relationship(back_populates="visits")
