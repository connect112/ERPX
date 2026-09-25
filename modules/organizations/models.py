"""
Organizations module — ORM models.

`Organization` is the tenant boundary for the whole platform: every
business record created by CRM, Students, Courses, Accounting, etc. will
carry an `organization_id` foreign key back to this table. GIR
Technologies runs ERPX as a multi-tenant product, so this table is the
root of that isolation.
"""

import enum

from sqlalchemy import Boolean, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import SoftDeleteMixin, TimestampedBase


class SubscriptionPlan(str, enum.Enum):
    TRIAL = "trial"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class Organization(TimestampedBase, SoftDeleteMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    industry: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    subscription_plan: Mapped[SubscriptionPlan] = mapped_column(
        SAEnum(
            SubscriptionPlan,
            name="subscription_plan",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        default=SubscriptionPlan.TRIAL,
        server_default=SubscriptionPlan.TRIAL.value,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Python's date.weekday() convention: Monday=0 .. Sunday=6. Attendance's
    # proration (and its own monthly summary) treats any day in this list
    # that has no attendance record as an implicit, paid Week Off — an
    # employee's self check-in only ever creates a record for a day they
    # actually worked, so a recurring weekly off needs a policy fact here,
    # not a per-day record. Defaults to Sunday-only, matching every org's
    # behavior before this became configurable.
    week_off_days: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), default=[6], server_default="{6}", nullable=False
    )
