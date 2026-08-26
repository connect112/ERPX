"""create placements_aggregation_runs and placements_aggregation_run_sources tables

Revision ID: 0043
Revises: 0042
Create Date: 2026-08-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

run_status_enum = postgresql.ENUM(
    "queued", "running", "completed", "failed", "skipped_no_ai",
    name="placements_aggregation_run_status",
)


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
    run_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "placements_aggregation_runs",
        *_tc(),
        sa.Column("triggered_by", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued", "running", "completed", "failed", "skipped_no_ai",
                name="placements_aggregation_run_status", create_type=False,
            ),
            nullable=False, server_default="queued",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("postings_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("postings_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("postings_closed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matches_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_placements_aggregation_runs_status", "placements_aggregation_runs", ["status"]
    )

    op.create_table(
        "placements_aggregation_run_sources",
        *_tc(),
        sa.Column(
            "aggregation_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("placements_aggregation_runs.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("postings_fetched", sa.Integer(), nullable=False, server_default="0"),
        # Summed by connectors/adzuna.py and connectors/jooble.py to enforce
        # Adzuna's daily and Jooble's *lifetime* free-tier call budgets
        # before making another request — see ADZUNA_DAILY_CALL_BUDGET /
        # JOOBLE_LIFETIME_CALL_BUDGET in app/core/config.py.
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_placements_aggregation_run_sources_aggregation_run_id",
        "placements_aggregation_run_sources",
        ["aggregation_run_id"],
    )
    op.create_index(
        "ix_placements_aggregation_run_sources_source_status",
        "placements_aggregation_run_sources",
        ["source", "status"],
    )


def downgrade() -> None:
    op.drop_table("placements_aggregation_run_sources")
    op.drop_table("placements_aggregation_runs")
    run_status_enum.drop(op.get_bind(), checkfirst=True)
