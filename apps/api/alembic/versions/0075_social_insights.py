"""social media phase 5a: account and post insights, experiments, reports

Revision ID: 0075
Revises: 0074
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0075"
down_revision: Union[str, None] = "0074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base() -> list:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _org() -> sa.Column:
    return sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "social_account_days",
        *_base(),
        _org(),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(60), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "day", "metric", name="uq_social_account_day_metric"),
    )
    op.create_index("ix_social_account_days_organization_id", "social_account_days", ["organization_id"])

    op.create_table(
        "social_media_metrics",
        *_base(),
        _org(),
        sa.Column("media_external_id", sa.String(100), nullable=False),
        sa.Column("metric", sa.String(60), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "media_external_id", "metric", name="uq_social_media_metric"),
    )
    op.create_index("ix_social_media_metrics_organization_id", "social_media_metrics", ["organization_id"])
    op.create_index("ix_social_media_metrics_media_external_id", "social_media_metrics", ["media_external_id"])

    op.create_table(
        "social_experiments",
        *_base(),
        _org(),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("hypothesis", sa.String(600), nullable=False),
        sa.Column("variable", sa.String(30), nullable=False),
        sa.Column("metric", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), server_default="planned", nullable=False),
        sa.Column("audience", sa.String(300), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("ended_on", sa.Date(), nullable=True),
        sa.Column("variants", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("conclusion", sa.Text(), nullable=True),
    )
    op.create_index("ix_social_experiments_organization_id", "social_experiments", ["organization_id"])

    op.create_table(
        "social_reports",
        *_base(),
        _org(),
        sa.Column("generated_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("data", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.UniqueConstraint("organization_id", "kind", "period_start", name="uq_social_report_period"),
    )
    op.create_index("ix_social_reports_organization_id", "social_reports", ["organization_id"])


def downgrade() -> None:
    for table in ("social_reports", "social_experiments", "social_media_metrics", "social_account_days"):
        op.drop_table(table)
