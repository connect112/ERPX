"""offer letter generator: settings, branding images, generated letters, deliveries, audit trail

Revision ID: 0088
Revises: 0087
Create Date: 2026-10-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0088"
down_revision: Union[str, None] = "0087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _base(*extra):
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *extra,
    ]


def _org():
    return sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)


def _user(name):
    return sa.Column(name, _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


def upgrade() -> None:
    op.create_table(
        "offer_letter_settings",
        *_base(
            _org(),
            sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=True),
            sa.Column("config", postgresql.JSONB, server_default="{}", nullable=False),
            _user("updated_by_user_id"),
            sa.Column("approved_hash", sa.String(64), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            _user("approved_by_user_id"),
        ),
    )
    op.create_index("ix_offer_letter_settings_organization_id", "offer_letter_settings", ["organization_id"])
    op.create_index("uq_offer_letter_setting_org", "offer_letter_settings", ["organization_id"], unique=True, postgresql_where=sa.text("internship_id IS NULL"))
    op.create_index("uq_offer_letter_setting_internship", "offer_letter_settings", ["internship_id"], unique=True, postgresql_where=sa.text("internship_id IS NOT NULL"))

    op.create_table(
        "offer_letter_assets",
        *_base(
            _org(),
            sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=True),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(50), nullable=False),
            sa.Column("size_bytes", sa.Integer, nullable=False),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("data", sa.LargeBinary, nullable=False),
            _user("uploaded_by_user_id"),
        ),
    )
    op.create_index("ix_offer_letter_assets_organization_id", "offer_letter_assets", ["organization_id"])
    op.create_index("uq_offer_letter_asset_org", "offer_letter_assets", ["organization_id", "kind"], unique=True, postgresql_where=sa.text("internship_id IS NULL"))
    op.create_index("uq_offer_letter_asset_internship", "offer_letter_assets", ["internship_id", "kind"], unique=True, postgresql_where=sa.text("internship_id IS NOT NULL"))

    op.create_table(
        "offer_letters",
        *_base(
            _org(),
            sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False),
            sa.Column("selection_id", _UUID, sa.ForeignKey("our_internship_selections.id", ondelete="SET NULL"), nullable=True),
            sa.Column("student_id", _UUID, sa.ForeignKey("institution_students.id", ondelete="SET NULL"), nullable=True),
            sa.Column("version", sa.Integer, server_default="1", nullable=False),
            sa.Column("is_current", sa.Boolean, server_default=sa.text("true"), nullable=False),
            sa.Column("reference", sa.String(60), nullable=False),
            sa.Column("student_name", sa.String(255), nullable=False),
            sa.Column("student_email", sa.String(255), nullable=False),
            sa.Column("institution_name", sa.String(255), nullable=False),
            sa.Column("status", sa.String(20), server_default="pending", nullable=False),
            sa.Column("error", sa.String(500), nullable=True),
            sa.Column("filename", sa.String(255), nullable=True),
            sa.Column("pdf_data", sa.LargeBinary, nullable=True),
            sa.Column("pdf_size", sa.Integer, nullable=True),
            sa.Column("page_count", sa.Integer, nullable=True),
            sa.Column("data_hash", sa.String(64), nullable=True),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
            _user("generated_by_user_id"),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            _user("approved_by_user_id"),
            sa.Column("delivery_status", sa.String(20), server_default="none", nullable=False),
            sa.Column("delivery_attempts", sa.Integer, server_default="0", nullable=False),
            sa.Column("delivery_error", sa.String(500), nullable=True),
            sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
            _user("released_by_user_id"),
            sa.Column("sent_to_email", sa.String(255), nullable=True),
            sa.UniqueConstraint("selection_id", "version", name="uq_offer_letter_version"),
        ),
    )
    op.create_index("ix_offer_letters_organization_id", "offer_letters", ["organization_id"])
    op.create_index("uq_offer_letter_current", "offer_letters", ["selection_id"], unique=True, postgresql_where=sa.text("is_current"))
    op.create_index("ix_offer_letters_internship_current", "offer_letters", ["internship_id", "is_current"])

    op.create_table(
        "offer_letter_deliveries",
        *_base(
            _org(),
            sa.Column("letter_id", _UUID, sa.ForeignKey("offer_letters.id", ondelete="CASCADE"), nullable=False),
            sa.Column("recipient_email", sa.String(255), nullable=False),
            sa.Column("subject", sa.String(255), nullable=True),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("attempt", sa.Integer, server_default="1", nullable=False),
            sa.Column("error", sa.String(500), nullable=True),
        ),
    )
    op.create_index("ix_offer_letter_deliveries_organization_id", "offer_letter_deliveries", ["organization_id"])
    op.create_index("ix_offer_letter_deliveries_letter_id", "offer_letter_deliveries", ["letter_id"])

    op.create_table(
        "offer_letter_events",
        *_base(
            _org(),
            sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=True),
            sa.Column("letter_id", _UUID, sa.ForeignKey("offer_letters.id", ondelete="SET NULL"), nullable=True),
            _user("actor_user_id"),
            sa.Column("action", sa.String(40), nullable=False),
            sa.Column("detail", sa.Text, nullable=True),
        ),
    )
    op.create_index("ix_offer_letter_events_organization_id", "offer_letter_events", ["organization_id"])
    op.create_index("ix_offer_letter_events_internship_id", "offer_letter_events", ["internship_id"])


def downgrade() -> None:
    for table in ("offer_letter_events", "offer_letter_deliveries", "offer_letters", "offer_letter_assets", "offer_letter_settings"):
        op.drop_table(table)
