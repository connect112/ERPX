"""
Edited wording for the emails ERPX sends.

The defaults live in code (`packages/email/registry.py`); a row here overrides one template's subject
and body for an organisation, or, with `hackathon_id`, for a single hackathon (event emails only).
Deleting the row brings the default back.
"""

import uuid

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_model import TimestampedBase


class EmailTemplate(TimestampedBase):
    __tablename__ = "email_templates"
    __table_args__ = (
        # One edit per template per organisation, and one per template per hackathon.
        Index(
            "uq_email_template_org",
            "organization_id",
            "key",
            unique=True,
            postgresql_where=text("hackathon_id IS NULL"),
        ),
        Index(
            "uq_email_template_hackathon",
            "organization_id",
            "key",
            "hackathon_id",
            unique=True,
            postgresql_where=text("hackathon_id IS NOT NULL"),
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hackathon_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=True, index=True
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
