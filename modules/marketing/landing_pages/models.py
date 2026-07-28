"""
Marketing / Landing Pages — ORM models.

Named `landing_pages` (underscore) rather than matching the spec's
`landing-pages` folder verbatim — a hyphen isn't valid in a Python
package name — the same convention already used for
`courses/learning_paths` and `examinations/question_bank`; the original
hyphenated folder stays as an empty placeholder for structural parity
with the spec.

There is no stored `view_count`: `LandingPageView` is an append-only
event log, and view/conversion counts are computed live in
`service.py` by aggregating it, the same principle used everywhere
else a running total would otherwise risk drifting under concurrent
writes.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.crm.leads.models import Lead  # noqa: F401
from modules.marketing.campaigns.models import Campaign  # noqa: F401
from modules.organizations.models import Organization  # noqa: F401


class LandingPageStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class LandingPage(TimestampedBase):
    __tablename__ = "marketing_landing_pages"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_landing_page_org_slug"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )

    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LandingPageStatus] = mapped_column(
        SAEnum(LandingPageStatus, name="landing_page_status", values_callable=_values),
        default=LandingPageStatus.DRAFT,
        server_default=LandingPageStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LandingPageView(TimestampedBase):
    __tablename__ = "marketing_landing_page_views"

    landing_page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("marketing_landing_pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    converted_to_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("crm_leads.id", ondelete="SET NULL"), nullable=True, index=True
    )

    utm_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(100), nullable=True)
    referrer_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
