"""create crm tables (leads, enquiries, followups, counselling, admissions)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

lead_source_enum = postgresql.ENUM(
    "website", "referral", "social_media", "walk_in", "advertisement", "event", "other",
    name="lead_source",
)
lead_status_enum = postgresql.ENUM(
    "new", "contacted", "qualified", "converted", "lost", name="lead_status"
)
enquiry_status_enum = postgresql.ENUM("open", "in_progress", "closed", name="enquiry_status")
followup_type_enum = postgresql.ENUM(
    "call", "email", "meeting", "whatsapp", "other", name="followup_type"
)
followup_status_enum = postgresql.ENUM(
    "scheduled", "completed", "cancelled", "missed", name="followup_status"
)
counselling_mode_enum = postgresql.ENUM("online", "offline", "phone", name="counselling_mode")
counselling_status_enum = postgresql.ENUM(
    "scheduled", "completed", "cancelled", "no_show", name="counselling_status"
)
admission_status_enum = postgresql.ENUM("on_hold", "confirmed", "cancelled", name="admission_status")


def _timestamp_columns():
    return [
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    for enum_type in (
        lead_source_enum, lead_status_enum, enquiry_status_enum, followup_type_enum,
        followup_status_enum, counselling_mode_enum, counselling_status_enum, admission_status_enum,
    ):
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "crm_leads",
        *_timestamp_columns(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("source", postgresql.ENUM(
            "website", "referral", "social_media", "walk_in", "advertisement", "event", "other",
            name="lead_source", create_type=False,
        ), nullable=False, server_default="other"),
        sa.Column("status", postgresql.ENUM(
            "new", "contacted", "qualified", "converted", "lost", name="lead_status", create_type=False,
        ), nullable=False, server_default="new"),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("lost_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_crm_leads_organization_id", "crm_leads", ["organization_id"])
    op.create_index("ix_crm_leads_branch_id", "crm_leads", ["branch_id"])
    op.create_index("ix_crm_leads_status", "crm_leads", ["status"])
    op.create_index("ix_crm_leads_assigned_to_user_id", "crm_leads", ["assigned_to_user_id"])

    op.create_table(
        "crm_enquiries",
        *_timestamp_columns(),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_interest", sa.String(length=255), nullable=False),
        sa.Column("budget", sa.Numeric(12, 2), nullable=True),
        sa.Column("preferred_batch_timing", sa.String(length=150), nullable=True),
        sa.Column("status", postgresql.ENUM(
            "open", "in_progress", "closed", name="enquiry_status", create_type=False,
        ), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_crm_enquiries_lead_id", "crm_enquiries", ["lead_id"])

    op.create_table(
        "crm_followups",
        *_timestamp_columns(),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("follow_up_type", postgresql.ENUM(
            "call", "email", "meeting", "whatsapp", "other", name="followup_type", create_type=False,
        ), nullable=False, server_default="call"),
        sa.Column("status", postgresql.ENUM(
            "scheduled", "completed", "cancelled", "missed", name="followup_status", create_type=False,
        ), nullable=False, server_default="scheduled"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_crm_followups_lead_id", "crm_followups", ["lead_id"])

    op.create_table(
        "crm_counselling_sessions",
        *_timestamp_columns(),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("counselor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mode", postgresql.ENUM(
            "online", "offline", "phone", name="counselling_mode", create_type=False,
        ), nullable=False, server_default="phone"),
        sa.Column("status", postgresql.ENUM(
            "scheduled", "completed", "cancelled", "no_show", name="counselling_status", create_type=False,
        ), nullable=False, server_default="scheduled"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recommended_course", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_crm_counselling_sessions_lead_id", "crm_counselling_sessions", ["lead_id"])

    op.create_table(
        "crm_admissions",
        *_timestamp_columns(),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("course_name", sa.String(length=255), nullable=False),
        sa.Column("batch_name", sa.String(length=150), nullable=True),
        sa.Column("fee_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("admission_date", sa.Date(), nullable=False),
        sa.Column("status", postgresql.ENUM(
            "on_hold", "confirmed", "cancelled", name="admission_status", create_type=False,
        ), nullable=False, server_default="on_hold"),
        sa.UniqueConstraint("lead_id", name="uq_crm_admissions_lead_id"),
    )
    op.create_index("ix_crm_admissions_lead_id", "crm_admissions", ["lead_id"])
    op.create_index("ix_crm_admissions_organization_id", "crm_admissions", ["organization_id"])


def downgrade() -> None:
    op.drop_table("crm_admissions")
    op.drop_table("crm_counselling_sessions")
    op.drop_table("crm_followups")
    op.drop_table("crm_enquiries")
    op.drop_table("crm_leads")
    for enum_type in (
        admission_status_enum, counselling_status_enum, counselling_mode_enum,
        followup_status_enum, followup_type_enum, enquiry_status_enum,
        lead_status_enum, lead_source_enum,
    ):
        enum_type.drop(op.get_bind(), checkfirst=True)
