"""
Settings module — ORM models.

A simple per-organization key/value store (timezone, currency,
date format, fiscal year start, etc.). Modules read settings by key
rather than the schema growing a new column per module's preference.
"""

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase
from modules.organizations.models import Organization  # noqa: F401  (FK target)


class OrganizationSetting(TimestampedBase):
    __tablename__ = "organization_settings"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_org_setting_key"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(150), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
