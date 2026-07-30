"""
Marketing / Coupons — ORM models.

`Coupon` is the reusable discount code definition; `CouponRedemption` is
an append-only record of each use. Usage-limit enforcement (`service.py`)
counts redemptions live rather than maintaining a mutable counter on
`Coupon`. Because a live count-then-insert is a check-then-act sequence,
`redeem_coupon` takes a `SELECT ... FOR UPDATE` lock on the coupon row so
concurrent redemptions of the same code serialize and cannot exceed the
configured limit.
`redeemed_against_type`/`redeemed_against_id` are an opaque reference
(e.g. "admission", "invoice") rather than a hard FK, since a coupon may
apply against different order types across modules.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.marketing.campaigns.models import Campaign  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class CouponDiscountType(str, enum.Enum):
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Coupon(TimestampedBase):
    __tablename__ = "marketing_coupons"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_coupon_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    discount_type: Mapped[CouponDiscountType] = mapped_column(
        SAEnum(CouponDiscountType, name="coupon_discount_type", values_callable=_values), nullable=False
    )
    discount_value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    max_discount_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    min_order_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    usage_limit_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_limit_per_customer: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CouponRedemption(TimestampedBase):
    __tablename__ = "marketing_coupon_redemptions"

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("marketing_coupons.id", ondelete="CASCADE"), nullable=False, index=True
    )

    redeemed_by_reference: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # e.g. a customer email or external contact identifier — stable across their redemptions
    redeemed_against_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    redeemed_against_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    order_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    discount_amount_applied: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
