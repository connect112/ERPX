"""
Corporate / Contracts — ORM models.

`Contract.quotation_id` optionally points back to the `Quotation` it was
created from; `Quotation` carries no reciprocal reference, so this is
the only module that depends on both Clients/Projects and Quotations.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.corporate.clients.models import Client  # noqa: F401
from modules.corporate.projects.models import Project  # noqa: F401
from modules.corporate.quotations.models import Quotation  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class ContractType(str, enum.Enum):
    PROJECT = "project"
    AMC = "amc"
    RETAINER = "retainer"
    SOC_SUBSCRIPTION = "soc_subscription"
    OTHER = "other"


class ContractStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    RENEWED = "renewed"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Contract(TimestampedBase):
    __tablename__ = "corporate_contracts"
    __table_args__ = (
        UniqueConstraint("organization_id", "contract_number", name="uq_contract_org_number"),
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
    quotation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("corporate_quotations.id", ondelete="SET NULL"), nullable=True
    )

    contract_number: Mapped[str] = mapped_column(String(50), nullable=False)
    contract_type: Mapped[ContractType] = mapped_column(
        SAEnum(ContractType, name="corporate_contract_type", values_callable=_values), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[ContractStatus] = mapped_column(
        SAEnum(ContractStatus, name="corporate_contract_status", values_callable=_values),
        default=ContractStatus.DRAFT,
        server_default=ContractStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
