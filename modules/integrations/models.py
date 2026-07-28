"""
Integrations module — registry of third-party service connections.

This is a config registry, not a set of provider-specific OAuth flows —
there's no real Zoom/Slack/Razorpay credentials available in this
codebase to build a genuine OAuth handshake against. What IS real:
`IntegrationService.test_connection()` performs an actual outbound HTTP
request to the integration's configured `base_url` and records whatever
the endpoint actually returns — not a simulated/hardcoded success.
`api_key` is never returned in full through the API; `IntegrationPublic`
only exposes a masked suffix, matching how secrets are handled
everywhere real credentials are stored.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class IntegrationTestStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


def _values(enum_cls):
    return [m.value for m in enum_cls]


class Integration(TimestampedBase):
    __tablename__ = "integrations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_status: Mapped[IntegrationTestStatus | None] = mapped_column(
        SAEnum(IntegrationTestStatus, name="integration_test_status", values_callable=_values),
        nullable=True,
    )
    last_test_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
