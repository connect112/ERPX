"""offer-letter emails: a pending onboarding token, and what a release pins

Revision ID: 0101
Revises: 0100
Create Date: 2026-11-06

Additive only: every column is nullable and nothing is backfilled, so letters already queued or sent keep working
(a letter with no pinned template resolves its email when it is sent, as before).

- internship_onboarding_applications: a second, short-lived token slot. An email that carries a new link first stores the
  link's HASH here; it becomes the active token only once the mail server has accepted the message (or the student first uses
  it). The raw token is never stored.
- offer_letters: what one release decided (the Studio template version, the link policy, who authorised a legacy fallback)
  and a short lease so two workers cannot send the same letter at once.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0101"
down_revision: Union[str, None] = "0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("internship_onboarding_applications", sa.Column("pending_token_hash", sa.String(64), nullable=True))
    op.add_column("internship_onboarding_applications", sa.Column("pending_token_issued_at", sa.DateTime(timezone=True), nullable=True))
    # not secret: which delivery the pending token belongs to ("ol:<letter id hex>:<batch id hex>")
    op.add_column("internship_onboarding_applications", sa.Column("pending_token_ref", sa.String(80), nullable=True))
    op.create_index(
        "uq_onboarding_pending_token", "internship_onboarding_applications", ["pending_token_hash"], unique=True,
        postgresql_where=sa.text("pending_token_hash IS NOT NULL"),
    )

    op.add_column("offer_letters", sa.Column("release_batch_id", _UUID, nullable=True))
    op.add_column("offer_letters", sa.Column("email_source", sa.String(20), nullable=True))
    op.add_column("offer_letters", sa.Column(
        "email_version_id", _UUID, sa.ForeignKey("email_studio_versions.id", ondelete="SET NULL"), nullable=True))
    op.add_column("offer_letters", sa.Column("email_link_policy", sa.String(20), nullable=True))
    op.add_column("offer_letters", sa.Column(
        "email_fallback_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("offer_letters", sa.Column("delivery_lease_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for column in ("delivery_lease_until", "email_fallback_by_user_id", "email_link_policy", "email_version_id", "email_source", "release_batch_id"):
        op.drop_column("offer_letters", column)
    op.drop_index("uq_onboarding_pending_token", table_name="internship_onboarding_applications")
    for column in ("pending_token_ref", "pending_token_issued_at", "pending_token_hash"):
        op.drop_column("internship_onboarding_applications", column)
