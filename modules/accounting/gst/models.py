"""
Accounting / GST — ORM models.

`GSTRate` is the only stored table: a rate config (e.g. "GST 18%") that
Invoice/Expense lines reference. There is no stored "GST return" table —
GSTR-style summaries are computed live in `service.py` by aggregating
tax already recorded on Invoice/Expense lines for a period, the same
"no redundant table" principle used for the Ledger's account balances.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.organizations.models import Organization  # noqa: F401


class GSTRate(TimestampedBase):
    __tablename__ = "accounting_gst_rates"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_gst_rate_org_name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rate_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    hsn_sac_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def half_rate_percent(self) -> float:
        """CGST/SGST each carry half the total rate on an intra-state supply."""
        return float(self.rate_percent) / 2
