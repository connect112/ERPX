"""email studio: designed templates and versions, brand profiles, signatures, components, assignments, images, send history

Revision ID: 0089
Revises: 0088
Create Date: 2026-10-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0089"
down_revision: Union[str, None] = "0088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)
_FALSE = sa.text("false")


def _base(*extra):
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *extra,
    ]


def _org(nullable=False):
    return sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=nullable)


def _user(name):
    return sa.Column(name, _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


def _text(name, length, default=""):
    return sa.Column(name, sa.String(length), nullable=False, server_default=default)


def upgrade() -> None:
    op.create_table(
        "email_studio_assets",
        *_base(
            _org(),
            sa.Column("token", sa.String(48), nullable=False, unique=True),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(50), nullable=False),
            sa.Column("size_bytes", sa.Integer, nullable=False),
            sa.Column("data", sa.LargeBinary, nullable=False),
            _user("uploaded_by_user_id"),
        ),
    )
    op.create_index("ix_email_studio_assets_organization_id", "email_studio_assets", ["organization_id"])

    op.create_table(
        "email_brand_profiles",
        *_base(
            _org(),
            sa.Column("name", sa.String(120), nullable=False),
            _text("company_name", 200),
            sa.Column("logo_asset_id", _UUID, sa.ForeignKey("email_studio_assets.id", ondelete="SET NULL"), nullable=True),
            _text("primary_color", 7, "#2563eb"),
            _text("secondary_color", 7, "#1e40af"),
            _text("accent_color", 7, "#f59e0b"),
            _text("background_color", 7, "#f4f4f5"),
            _text("text_color", 7, "#111827"),
            _text("website", 300),
            _text("contact_email", 255),
            _text("phone", 60),
            _text("address", 500),
            _text("tagline", 200),
            sa.Column("social_links", postgresql.JSONB, nullable=False, server_default="[]"),
            _text("from_name", 120),
            _text("reply_to", 255),
            sa.Column("is_default", sa.Boolean, nullable=False, server_default=_FALSE),
            _user("updated_by_user_id"),
        ),
    )
    op.create_index("ix_email_brand_profiles_organization_id", "email_brand_profiles", ["organization_id"])

    op.create_table(
        "email_signatures",
        *_base(
            _org(),
            sa.Column("name", sa.String(120), nullable=False),
            _text("scope", 20, "company"),
            _text("person_name", 200),
            _text("designation", 200),
            _text("company_name", 200),
            _text("email", 255),
            _text("phone", 60),
            _text("website", 300),
            sa.Column("logo_asset_id", _UUID, sa.ForeignKey("email_studio_assets.id", ondelete="SET NULL"), nullable=True),
            sa.Column("signature_asset_id", _UUID, sa.ForeignKey("email_studio_assets.id", ondelete="SET NULL"), nullable=True),
            _user("signature_approved_by_user_id"),
            sa.Column("signature_approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("style", postgresql.JSONB, nullable=False, server_default="{}"),
            sa.Column("is_default", sa.Boolean, nullable=False, server_default=_FALSE),
            _user("updated_by_user_id"),
        ),
    )
    op.create_index("ix_email_signatures_organization_id", "email_signatures", ["organization_id"])

    op.create_table(
        "email_components",
        *_base(
            _org(),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            _text("description", 300),
            sa.Column("html", sa.Text, nullable=False),
            _user("updated_by_user_id"),
        ),
    )
    op.create_index("ix_email_components_organization_id", "email_components", ["organization_id"])

    # templates and versions point at each other, so the published-version link is added after both exist
    op.create_table(
        "email_studio_templates",
        *_base(
            _org(),
            sa.Column("name", sa.String(200), nullable=False),
            _text("description", 500),
            _text("category", 60, "Custom Emails"),
            sa.Column("source_type", sa.String(20), nullable=False),
            sa.Column("module", sa.String(60), nullable=True),
            _text("status", 20, "draft"),
            sa.Column("published_version_id", _UUID, nullable=True),
            _user("created_by_user_id"),
            _user("updated_by_user_id"),
        ),
    )
    op.create_index("ix_email_studio_templates_organization_id", "email_studio_templates", ["organization_id"])

    op.create_table(
        "email_studio_versions",
        *_base(
            _org(),
            sa.Column("template_id", _UUID, sa.ForeignKey("email_studio_templates.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_number", sa.Integer, nullable=False),
            _text("state", 20, "draft"),
            _text("subject", 300),
            _text("preheader", 200),
            sa.Column("editor_json", postgresql.JSONB, nullable=True),
            sa.Column("html_source", sa.Text, nullable=True),
            sa.Column("body_html", sa.Text, nullable=False, server_default=""),
            sa.Column("body_text", sa.Text, nullable=False, server_default=""),
            sa.Column("code_template_key", sa.String(80), nullable=True),
            sa.Column("code_props", postgresql.JSONB, nullable=True),
            sa.Column("brand_profile_id", _UUID, sa.ForeignKey("email_brand_profiles.id", ondelete="SET NULL"), nullable=True),
            sa.Column("signature_id", _UUID, sa.ForeignKey("email_signatures.id", ondelete="SET NULL"), nullable=True),
            sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
            _user("created_by_user_id"),
            _user("published_by_user_id"),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("template_id", "version_number", name="uq_email_version_number"),
        ),
    )
    op.create_index("ix_email_studio_versions_organization_id", "email_studio_versions", ["organization_id"])
    op.create_index("ix_email_studio_versions_template_id", "email_studio_versions", ["template_id"])
    op.create_index("uq_email_version_one_draft", "email_studio_versions", ["template_id"], unique=True, postgresql_where=sa.text("state = 'draft'"))
    op.create_foreign_key(
        "fk_email_template_published_version", "email_studio_templates", "email_studio_versions", ["published_version_id"], ["id"], ondelete="SET NULL"
    )

    op.create_table(
        "email_template_assignments",
        *_base(
            _org(),
            sa.Column("key", sa.String(80), nullable=False),
            sa.Column("hackathon_id", _UUID, sa.ForeignKey("hackathons.id", ondelete="CASCADE"), nullable=True),
            sa.Column("template_id", _UUID, sa.ForeignKey("email_studio_templates.id", ondelete="CASCADE"), nullable=False),
            _user("assigned_by_user_id"),
        ),
    )
    op.create_index("ix_email_template_assignments_organization_id", "email_template_assignments", ["organization_id"])
    op.create_index("ix_email_template_assignments_template_id", "email_template_assignments", ["template_id"])
    op.create_index("uq_email_assignment_org", "email_template_assignments", ["organization_id", "key"], unique=True, postgresql_where=sa.text("hackathon_id IS NULL"))
    op.create_index(
        "uq_email_assignment_hackathon", "email_template_assignments", ["organization_id", "key", "hackathon_id"], unique=True, postgresql_where=sa.text("hackathon_id IS NOT NULL")
    )

    op.create_table(
        "email_send_records",
        *_base(
            _org(nullable=True),
            sa.Column("key", sa.String(80), nullable=True),
            sa.Column("module", sa.String(60), nullable=True),
            sa.Column("template_id", _UUID, sa.ForeignKey("email_studio_templates.id", ondelete="SET NULL"), nullable=True),
            sa.Column("version_id", _UUID, sa.ForeignKey("email_studio_versions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source", sa.String(20), nullable=True),
            sa.Column("recipient", sa.String(255), nullable=False),
            _text("subject", 300),
            _text("status", 20, "queued"),
            sa.Column("error", sa.String(500), nullable=True),
            sa.Column("attachments", sa.Integer, nullable=False, server_default="0"),
            sa.Column("is_test", sa.Boolean, nullable=False, server_default=_FALSE),
            sa.Column("idempotency_key", sa.String(120), nullable=True),
            _user("sent_by_user_id"),
        ),
    )
    op.create_index("ix_email_send_records_org_created", "email_send_records", ["organization_id", "created_at"])
    op.create_index(
        "uq_email_send_idempotency", "email_send_records", ["organization_id", "idempotency_key"], unique=True, postgresql_where=sa.text("idempotency_key IS NOT NULL")
    )


def downgrade() -> None:
    op.drop_table("email_send_records")
    op.drop_table("email_template_assignments")
    op.drop_constraint("fk_email_template_published_version", "email_studio_templates", type_="foreignkey")
    op.drop_table("email_studio_versions")
    op.drop_table("email_studio_templates")
    for table in ("email_components", "email_signatures", "email_brand_profiles", "email_studio_assets"):
        op.drop_table(table)
