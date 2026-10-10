"""social media phase 6: heartbeats of the scheduled jobs

Revision ID: 0077
Revises: 0076
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0077"
down_revision: Union[str, None] = "0076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "social_job_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("job", sa.String(40), nullable=False),
        sa.Column("last_finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_ok", sa.Boolean(), nullable=False),
        sa.Column("last_error", sa.String(300), nullable=True),
        sa.Column("last_count", sa.Integer(), nullable=True),
        sa.Column("detail", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("job", name="uq_social_job_runs_job"),
    )


def downgrade() -> None:
    op.drop_table("social_job_runs")
