"""
Corporate / Clients — ORM models.

`Client` is the B2B relationship record for GIR Technologies' corporate
services (VAPT, SOC, AMC, consulting) — a distinct concept from
Accounting's `Customer` (the AR billing record) even though the two
usually correspond 1:1. `accounting_customer_id` links to that billing
record when invoicing is set up, rather than duplicating billing fields
here; a Client can exist (e.g. during a sales cycle) before any invoice
is ever raised, so the link is nullable, not required.
"""

import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import SoftDeleteMixin, TimestampedBase
from modules.accounting.customers.models import Customer  # noqa: F401
from modules.authentication.models import User  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class ClientStatus(str, enum.Enum):
    PROSPECT = "prospect"
    ACTIVE = "active"
    INACTIVE = "inactive"
    CHURNED = "churned"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Client(TimestampedBase, SoftDeleteMixin):
    __tablename__ = "corporate_clients"
    __table_args__ = (UniqueConstraint("organization_id", "client_code", name="uq_corporate_client_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    accounting_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("accounting_customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    account_manager_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )

    client_code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)

    contact_person_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    status: Mapped[ClientStatus] = mapped_column(
        SAEnum(ClientStatus, name="corporate_client_status", values_callable=_values),
        default=ClientStatus.PROSPECT,
        server_default=ClientStatus.PROSPECT.value,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
