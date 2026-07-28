"""
Marketing / Campaigns — ORM models.

`Campaign` is the attribution anchor every other Marketing sub-module
(and CRM's `Lead.campaign_id`) references, so lead generation, landing
page views, coupon usage, and referral conversions can all be rolled
up per campaign in `analytics`.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401
from modules.branches.models import Branch  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class CampaignChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    SOCIAL_MEDIA = "social_media"
    GOOGLE_ADS = "google_ads"
    WHATSAPP = "whatsapp"
    EVENT = "event"
    OTHER = "other"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Campaign(TimestampedBase):
    __tablename__ = "marketing_campaigns"
    __table_args__ = (UniqueConstraint("organization_id", "campaign_code", name="uq_campaign_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    campaign_code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[CampaignChannel] = mapped_column(
        SAEnum(CampaignChannel, name="campaign_channel", values_callable=_values), nullable=False, index=True
    )
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(CampaignStatus, name="campaign_status", values_callable=_values),
        default=CampaignStatus.DRAFT,
        server_default=CampaignStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    budget_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    actual_spend: Mapped[float] = mapped_column(Numeric(14, 2), default=0, server_default="0", nullable=False)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
