"""create alumni profiles, events, registrations, job referrals tables

Revision ID: 0028
Revises: 0027
Create Date: 2026-07-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

event_mode_enum = postgresql.ENUM("physical", "virtual", name="alumni_event_mode")
event_status_enum = postgresql.ENUM("draft", "published", "completed", "cancelled", name="alumni_event_status")
registration_status_enum = postgresql.ENUM(
    "registered", "attended", "cancelled", name="alumni_registration_status"
)
referral_status_enum = postgresql.ENUM("open", "closed", name="alumni_referral_status")

_ALL_ENUMS = [event_mode_enum, event_status_enum, registration_status_enum, referral_status_enum]


def _tc():
    return [
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    for enum_type in _ALL_ENUMS:
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "alumni_profiles",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("graduation_year", sa.Integer(), nullable=True),
        sa.Column("current_company", sa.String(length=255), nullable=True),
        sa.Column("current_designation", sa.String(length=255), nullable=True),
        sa.Column("current_location", sa.String(length=255), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_alumni_profiles_organization_id", "alumni_profiles", ["organization_id"])

    op.create_table(
        "alumni_events",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "mode", postgresql.ENUM("physical", "virtual", name="alumni_event_mode", create_type=False),
            nullable=False, server_default="virtual",
        ),
        sa.Column("venue", sa.String(length=255), nullable=True),
        sa.Column("meeting_link", sa.String(length=500), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("registration_deadline", sa.Date(), nullable=True),
        sa.Column(
            "status", postgresql.ENUM("draft", "published", "completed", "cancelled", name="alumni_event_status", create_type=False),
            nullable=False, server_default="draft",
        ),
    )
    op.create_index("ix_alumni_events_organization_id", "alumni_events", ["organization_id"])
    op.create_index("ix_alumni_events_status", "alumni_events", ["status"])

    op.create_table(
        "alumni_event_registrations",
        *_tc(),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alumni_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alumni_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alumni_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", postgresql.ENUM("registered", "attended", "cancelled", name="alumni_registration_status", create_type=False),
            nullable=False, server_default="registered",
        ),
        sa.UniqueConstraint("event_id", "alumni_id", name="uq_alumni_event_registration"),
    )
    op.create_index("ix_alumni_event_registrations_event_id", "alumni_event_registrations", ["event_id"])
    op.create_index("ix_alumni_event_registrations_alumni_id", "alumni_event_registrations", ["alumni_id"])
    op.create_index("ix_alumni_event_registrations_status", "alumni_event_registrations", ["status"])

    op.create_table(
        "alumni_job_referrals",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alumni_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alumni_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("referral_link", sa.String(length=500), nullable=True),
        sa.Column(
            "status", postgresql.ENUM("open", "closed", name="alumni_referral_status", create_type=False),
            nullable=False, server_default="open",
        ),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_alumni_job_referrals_organization_id", "alumni_job_referrals", ["organization_id"])
    op.create_index("ix_alumni_job_referrals_alumni_id", "alumni_job_referrals", ["alumni_id"])
    op.create_index("ix_alumni_job_referrals_status", "alumni_job_referrals", ["status"])


def downgrade() -> None:
    op.drop_table("alumni_job_referrals")
    op.drop_table("alumni_event_registrations")
    op.drop_table("alumni_events")
    op.drop_table("alumni_profiles")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
