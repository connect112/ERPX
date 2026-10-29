"""pentrix marketing: templates made available for it, suppressions, campaigns and their recipients; the candidate's marketing choice

Revision ID: 0094
Revises: 0093
Create Date: 2026-10-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0094"
down_revision: Union[str, None] = "0093"
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


def upgrade() -> None:
    # Nobody is opted in until Pentrix says so: an explicit choice each person makes themselves.
    op.add_column("pentrix_candidates", sa.Column("marketing_opt_in", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("pentrix_candidates", sa.Column("marketing_changed_at", sa.DateTime(timezone=True)))

    op.create_table(
        "pentrix_marketing_templates",
        *_base(
            sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("template_id", _UUID, sa.ForeignKey("email_studio_templates.id", ondelete="CASCADE"), nullable=False),
            sa.Column("campaign_name", sa.String(200), nullable=False),
            sa.Column("available_from", sa.Date),
            sa.Column("available_until", sa.Date),
            sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        ),
    )
    op.create_unique_constraint("uq_pentrix_marketing_template", "pentrix_marketing_templates", ["organization_id", "template_id"])
    op.create_index("ix_pentrix_marketing_templates_organization_id", "pentrix_marketing_templates", ["organization_id"])
    op.create_index("ix_pentrix_marketing_templates_template_id", "pentrix_marketing_templates", ["template_id"])

    op.create_table(
        "pentrix_marketing_suppressions",
        *_base(
            sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("pentrix_user_id", sa.String(36)),
            sa.Column("source", sa.String(30), nullable=False, server_default="unsubscribe_link"),
            sa.Column("pentrix_synced", sa.Boolean, nullable=False, server_default="false"),
        ),
    )
    op.create_unique_constraint("uq_pentrix_marketing_suppression", "pentrix_marketing_suppressions", ["organization_id", "email"])
    op.create_index("ix_pentrix_marketing_suppressions_organization_id", "pentrix_marketing_suppressions", ["organization_id"])
    op.create_index("ix_pentrix_marketing_suppressions_pentrix_user_id", "pentrix_marketing_suppressions", ["pentrix_user_id"])

    op.create_table(
        "pentrix_marketing_campaigns",
        *_base(
            sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("template_id", _UUID, sa.ForeignKey("email_studio_templates.id", ondelete="SET NULL")),
            sa.Column("version_id", _UUID, sa.ForeignKey("email_studio_versions.id", ondelete="SET NULL")),
            sa.Column("campaign_name", sa.String(200), nullable=False),
            sa.Column("subject", sa.String(300), nullable=False, server_default=""),
            sa.Column("brand_profile_id", _UUID, sa.ForeignKey("email_brand_profiles.id", ondelete="SET NULL")),
            sa.Column("signature_id", _UUID, sa.ForeignKey("email_signatures.id", ondelete="SET NULL")),
            sa.Column("status", sa.String(12), nullable=False, server_default="sending"),
            sa.Column("recipient_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("excluded", postgresql.JSONB),
            sa.Column("selection", postgresql.JSONB),
            sa.Column("idempotency_key", sa.String(80), nullable=False),
            sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
        ),
    )
    op.create_index("ix_pentrix_marketing_campaigns_organization_id", "pentrix_marketing_campaigns", ["organization_id"])
    op.create_index("uq_pentrix_campaign_idempotency", "pentrix_marketing_campaigns", ["organization_id", "idempotency_key"], unique=True)

    op.create_table(
        "pentrix_marketing_recipients",
        *_base(
            sa.Column("campaign_id", _UUID, sa.ForeignKey("pentrix_marketing_campaigns.id", ondelete="CASCADE"), nullable=False),
            sa.Column("pentrix_user_id", sa.String(36), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("name", sa.String(255), nullable=False, server_default=""),
            sa.Column("status", sa.String(10), nullable=False, server_default="queued"),
            sa.Column("error", sa.String(500)),
            sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
            sa.Column("claimed_at", sa.DateTime(timezone=True)),
            sa.Column("sent_at", sa.DateTime(timezone=True)),
        ),
    )
    op.create_unique_constraint("uq_pentrix_campaign_recipient", "pentrix_marketing_recipients", ["campaign_id", "email"])
    op.create_index("ix_pentrix_marketing_recipients_campaign_id", "pentrix_marketing_recipients", ["campaign_id"])
    op.create_index("ix_pentrix_campaign_recipient_status", "pentrix_marketing_recipients", ["campaign_id", "status"])


def downgrade() -> None:
    op.drop_table("pentrix_marketing_recipients")
    op.drop_table("pentrix_marketing_campaigns")
    op.drop_table("pentrix_marketing_suppressions")
    op.drop_table("pentrix_marketing_templates")
    op.drop_column("pentrix_candidates", "marketing_changed_at")
    op.drop_column("pentrix_candidates", "marketing_opt_in")
