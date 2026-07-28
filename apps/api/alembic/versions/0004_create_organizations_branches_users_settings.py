"""create organizations, branches, user_profiles, organization_settings

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

subscription_plan_enum = postgresql.ENUM(
    "trial", "basic", "professional", "enterprise", name="subscription_plan"
)
gender_enum = postgresql.ENUM(
    "male", "female", "other", "prefer_not_to_say", name="gender"
)


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
    subscription_plan_enum.create(op.get_bind(), checkfirst=True)
    gender_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "organizations",
        *_timestamp_columns(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("industry", sa.String(length=150), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column(
            "subscription_plan",
            postgresql.ENUM(
                "trial", "basic", "professional", "enterprise",
                name="subscription_plan", create_type=False,
            ),
            nullable=False,
            server_default="trial",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    op.create_table(
        "branches",
        *_timestamp_columns(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("is_head_office", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_branch_org_code"),
    )
    op.create_index("ix_branches_organization_id", "branches", ["organization_id"])

    op.create_table(
        "user_profiles",
        *_timestamp_columns(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("employee_code", sa.String(length=50), nullable=True),
        sa.Column("designation", sa.String(length=150), nullable=True),
        sa.Column("department", sa.String(length=150), nullable=True),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column(
            "gender",
            postgresql.ENUM(
                "male", "female", "other", "prefer_not_to_say",
                name="gender", create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("date_of_joining", sa.Date(), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"])
    op.create_index("ix_user_profiles_organization_id", "user_profiles", ["organization_id"])
    op.create_index("ix_user_profiles_branch_id", "user_profiles", ["branch_id"])

    op.create_table(
        "organization_settings",
        *_timestamp_columns(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(length=150), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.UniqueConstraint("organization_id", "key", name="uq_org_setting_key"),
    )
    op.create_index("ix_organization_settings_organization_id", "organization_settings", ["organization_id"])


def downgrade() -> None:
    op.drop_table("organization_settings")
    op.drop_table("user_profiles")
    op.drop_table("branches")
    op.drop_table("organizations")
    gender_enum.drop(op.get_bind(), checkfirst=True)
    subscription_plan_enum.drop(op.get_bind(), checkfirst=True)
