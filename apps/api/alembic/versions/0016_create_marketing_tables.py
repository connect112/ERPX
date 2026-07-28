"""create marketing tables (campaigns, landing pages, coupons, referrals) and crm_leads.campaign_id

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

campaign_channel_enum = postgresql.ENUM("email", "sms", "social_media", "google_ads", "whatsapp", "event", "other", name="campaign_channel")
campaign_status_enum = postgresql.ENUM("draft", "scheduled", "active", "paused", "completed", "cancelled", name="campaign_status")
landing_page_status_enum = postgresql.ENUM("draft", "published", "archived", name="landing_page_status")
coupon_discount_type_enum = postgresql.ENUM("percentage", "fixed_amount", name="coupon_discount_type")
referral_status_enum = postgresql.ENUM("pending", "converted", "rewarded", "expired", "rejected", name="referral_status")

_ALL_ENUMS = [
    campaign_channel_enum,
    campaign_status_enum,
    landing_page_status_enum,
    coupon_discount_type_enum,
    referral_status_enum,
]


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

    # ---- Campaigns ----
    op.create_table(
        "marketing_campaigns",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("channel", postgresql.ENUM("email", "sms", "social_media", "google_ads", "whatsapp", "event", "other", name="campaign_channel", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("draft", "scheduled", "active", "paused", "completed", "cancelled", name="campaign_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("budget_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("actual_spend", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "campaign_code", name="uq_campaign_org_code"),
    )
    op.create_index("ix_marketing_campaigns_organization_id", "marketing_campaigns", ["organization_id"])
    op.create_index("ix_marketing_campaigns_channel", "marketing_campaigns", ["channel"])
    op.create_index("ix_marketing_campaigns_status", "marketing_campaigns", ["status"])

    # `crm_leads` gains an optional attribution link now that `marketing_campaigns` exists.
    op.add_column(
        "crm_leads",
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_crm_leads_campaign_id", "crm_leads", ["campaign_id"])

    # ---- Landing Pages ----
    op.create_table(
        "marketing_landing_pages",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("meta_description", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", postgresql.ENUM("draft", "published", "archived", name="landing_page_status", create_type=False), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "slug", name="uq_landing_page_org_slug"),
    )
    op.create_index("ix_marketing_landing_pages_organization_id", "marketing_landing_pages", ["organization_id"])
    op.create_index("ix_marketing_landing_pages_campaign_id", "marketing_landing_pages", ["campaign_id"])
    op.create_index("ix_marketing_landing_pages_status", "marketing_landing_pages", ["status"])

    op.create_table(
        "marketing_landing_page_views",
        *_tc(),
        sa.Column("landing_page_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketing_landing_pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("converted_to_lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("utm_source", sa.String(length=100), nullable=True),
        sa.Column("utm_medium", sa.String(length=100), nullable=True),
        sa.Column("utm_campaign", sa.String(length=100), nullable=True),
        sa.Column("referrer_url", sa.String(length=512), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_marketing_landing_page_views_landing_page_id", "marketing_landing_page_views", ["landing_page_id"])
    op.create_index("ix_marketing_landing_page_views_converted_to_lead_id", "marketing_landing_page_views", ["converted_to_lead_id"])
    op.create_index("ix_marketing_landing_page_views_viewed_at", "marketing_landing_page_views", ["viewed_at"])

    # ---- Coupons ----
    op.create_table(
        "marketing_coupons",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("discount_type", postgresql.ENUM("percentage", "fixed_amount", name="coupon_discount_type", create_type=False), nullable=False),
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_discount_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("min_order_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("usage_limit_total", sa.Integer(), nullable=True),
        sa.Column("usage_limit_per_customer", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_coupon_org_code"),
    )
    op.create_index("ix_marketing_coupons_organization_id", "marketing_coupons", ["organization_id"])
    op.create_index("ix_marketing_coupons_campaign_id", "marketing_coupons", ["campaign_id"])

    op.create_table(
        "marketing_coupon_redemptions",
        *_tc(),
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketing_coupons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("redeemed_by_reference", sa.String(length=255), nullable=False),
        sa.Column("redeemed_against_type", sa.String(length=50), nullable=True),
        sa.Column("redeemed_against_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount_applied", sa.Numeric(14, 2), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_marketing_coupon_redemptions_coupon_id", "marketing_coupon_redemptions", ["coupon_id"])
    op.create_index("ix_marketing_coupon_redemptions_redeemed_by_reference", "marketing_coupon_redemptions", ["redeemed_by_reference"])
    op.create_index("ix_marketing_coupon_redemptions_redeemed_at", "marketing_coupon_redemptions", ["redeemed_at"])

    # ---- Referrals ----
    op.create_table(
        "marketing_referral_programs",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("referrer_reward_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("referee_discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("max_referrals_per_referrer", sa.Integer(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "code", name="uq_referral_program_org_code"),
    )
    op.create_index("ix_marketing_referral_programs_organization_id", "marketing_referral_programs", ["organization_id"])

    op.create_table(
        "marketing_referrals",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referral_program_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketing_referral_programs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("referrer_student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
        sa.Column("converted_lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("referee_name", sa.String(length=255), nullable=False),
        sa.Column("referee_email", sa.String(length=255), nullable=True),
        sa.Column("referee_phone", sa.String(length=32), nullable=True),
        sa.Column("status", postgresql.ENUM("pending", "converted", "rewarded", "expired", "rejected", name="referral_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("reward_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_marketing_referrals_organization_id", "marketing_referrals", ["organization_id"])
    op.create_index("ix_marketing_referrals_referral_program_id", "marketing_referrals", ["referral_program_id"])
    op.create_index("ix_marketing_referrals_referrer_student_id", "marketing_referrals", ["referrer_student_id"])
    op.create_index("ix_marketing_referrals_status", "marketing_referrals", ["status"])


def downgrade() -> None:
    op.drop_table("marketing_referrals")
    op.drop_table("marketing_referral_programs")
    op.drop_table("marketing_coupon_redemptions")
    op.drop_table("marketing_coupons")
    op.drop_table("marketing_landing_page_views")
    op.drop_table("marketing_landing_pages")
    op.drop_index("ix_crm_leads_campaign_id", table_name="crm_leads")
    op.drop_column("crm_leads", "campaign_id")
    op.drop_table("marketing_campaigns")
    for enum_type in reversed(_ALL_ENUMS):
        enum_type.drop(op.get_bind(), checkfirst=True)
