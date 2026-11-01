"""internship onboarding: configuration, templates, applications, documents, events

Revision ID: 0098
Revises: 0097
Create Date: 2026-10-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0098"
down_revision: Union[str, None] = "0097"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)
_JSONB = postgresql.JSONB


def _base() -> list:
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
    ]


def _user(name: str) -> sa.Column:
    return sa.Column(name, _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=True)


def upgrade() -> None:
    op.create_table(
        "internship_onboarding_templates",
        *_base(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("settings", _JSONB, nullable=False),
        sa.Column("archived", sa.Boolean, nullable=False, server_default="false"),
        _user("created_by_user_id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_onboarding_template_name"),
    )
    op.create_table(
        "internship_onboarding_template_versions",
        *_base(),
        sa.Column("template_id", _UUID, sa.ForeignKey("internship_onboarding_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("settings", _JSONB, nullable=False),
        _user("created_by_user_id"),
        sa.UniqueConstraint("template_id", "version", name="uq_onboarding_template_version"),
    )
    op.create_table(
        "internship_onboarding_configs",
        *_base(),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("settings", _JSONB, nullable=False),
        sa.Column("template_id", _UUID, sa.ForeignKey("internship_onboarding_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("template_version", sa.Integer, nullable=True),
        _user("updated_by_user_id"),
    )
    op.create_table(
        "internship_onboarding_config_versions",
        *_base(),
        sa.Column("config_id", _UUID, sa.ForeignKey("internship_onboarding_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("settings", _JSONB, nullable=False),
        _user("created_by_user_id"),
        sa.UniqueConstraint("config_id", "version", name="uq_onboarding_config_version"),
    )
    op.create_table(
        "internship_onboarding_counters",
        *_base(),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("last_value", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("organization_id", "year", name="uq_onboarding_counter"),
    )
    op.create_table(
        "internship_onboarding_applications",
        *_base(),
        sa.Column("internship_id", _UUID, sa.ForeignKey("our_internships.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selection_id", _UUID, sa.ForeignKey("our_internship_selections.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("reference", sa.String(40), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=True, unique=True),
        _ts("token_issued_at"),
        _ts("token_revoked_at"),
        _ts("started_at"),
        _ts("last_activity_at"),
        sa.Column("current_step", sa.String(30), nullable=False, server_default="welcome"),
        sa.Column("info_original", _JSONB, nullable=False, server_default="{}"),
        sa.Column("info_proposed", _JSONB, nullable=False, server_default="{}"),
        sa.Column("info_review_status", sa.String(20), nullable=False, server_default="none"),
        sa.Column("form_version", sa.Integer, nullable=True),
        sa.Column("form_responses", _JSONB, nullable=False, server_default="{}"),
        _ts("accepted_at"),
        _ts("declined_at"),
        sa.Column("decline_reason", sa.Text, nullable=True),
        sa.Column("terms_version", sa.String(20), nullable=True),
        sa.Column("declaration_text", sa.Text, nullable=True),
        sa.Column("config_version", sa.Integer, nullable=True),
        sa.Column("fee_snapshot", _JSONB, nullable=True),
        sa.Column("acceptance_meta", _JSONB, nullable=True),
        _ts("deadline_override_at"),
        _ts("reopened_at"),
        _user("reopened_by_user_id"),
        sa.Column("reopen_reason", sa.Text, nullable=True),
        _ts("completed_at"),
        _ts("cancelled_at"),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        sa.UniqueConstraint("organization_id", "reference", name="uq_onboarding_application_reference"),
    )
    op.create_index("ix_onboarding_applications_internship", "internship_onboarding_applications", ["internship_id"])
    op.create_table(
        "internship_onboarding_documents",
        *_base(),
        sa.Column("application_id", _UUID, sa.ForeignKey("internship_onboarding_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_key", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("filename", sa.String(160), nullable=False),
        sa.Column("content_type", sa.String(60), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(300), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        _user("reviewed_by_user_id"),
        _ts("reviewed_at"),
        sa.Column("review_note", sa.Text, nullable=True),
        sa.UniqueConstraint("application_id", "requirement_key", "version", name="uq_onboarding_document_version"),
    )
    op.create_table(
        "internship_onboarding_events",
        *_base(),
        sa.Column("application_id", _UUID, sa.ForeignKey("internship_onboarding_applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor", sa.String(10), nullable=False),
        _user("actor_user_id"),
        sa.Column("event", sa.String(40), nullable=False),
        sa.Column("detail", _JSONB, nullable=False, server_default="{}"),
    )
    for table, cols in (
        ("internship_onboarding_templates", ["organization_id"]),
        ("internship_onboarding_template_versions", ["organization_id", "template_id"]),
        ("internship_onboarding_configs", ["organization_id"]),
        ("internship_onboarding_config_versions", ["organization_id", "config_id"]),
        ("internship_onboarding_counters", ["organization_id"]),
        ("internship_onboarding_applications", ["organization_id"]),
        ("internship_onboarding_documents", ["organization_id", "application_id"]),
        ("internship_onboarding_events", ["organization_id", "application_id"]),
    ):
        for col in cols:
            op.create_index(f"ix_{table}_{col}", table, [col])


def downgrade() -> None:
    for table in (
        "internship_onboarding_events",
        "internship_onboarding_documents",
        "internship_onboarding_applications",
        "internship_onboarding_counters",
        "internship_onboarding_config_versions",
        "internship_onboarding_configs",
        "internship_onboarding_template_versions",
        "internship_onboarding_templates",
    ):
        op.drop_table(table)
