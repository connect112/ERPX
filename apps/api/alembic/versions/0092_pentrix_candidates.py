"""pentrix candidates: a synchronised summary of every Pentrix candidate

Revision ID: 0092
Revises: 0091
Create Date: 2026-10-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0092"
down_revision: Union[str, None] = "0091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "pentrix_candidates",
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pentrix_user_id", sa.String(36), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("email", sa.String(255), nullable=False, server_default=""),
        sa.Column("phone", sa.String(24)),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assessment_state", sa.String(16), nullable=False, server_default="not_started"),
        sa.Column("assessment_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("readiness_pct", sa.Float),
        sa.Column("technical_pct", sa.Float),
        sa.Column("qualified", sa.Boolean),
        sa.Column("assessed_at", sa.DateTime(timezone=True)),
        sa.Column("booking_pentrix_id", sa.String(36)),
        sa.Column("booking_status", sa.String(20)),
        sa.Column("booking_start", sa.DateTime(timezone=True)),
        sa.Column("booking_end", sa.DateTime(timezone=True)),
        sa.Column("payment_status", sa.String(12), nullable=False, server_default="none"),
        sa.Column("paid_total_paise", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("payment_currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("last_paid_at", sa.DateTime(timezone=True)),
        sa.Column("payment_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("enrolled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_activity_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_pentrix_candidates_organization_id", "pentrix_candidates", ["organization_id"])
    op.create_index("ix_pentrix_candidates_email", "pentrix_candidates", ["email"])
    op.create_unique_constraint("uq_pentrix_candidates_pentrix_user_id", "pentrix_candidates", ["pentrix_user_id"])
    op.create_index("ix_pentrix_candidates_org_registered", "pentrix_candidates", ["organization_id", "registered_at"])
    op.create_index("ix_pentrix_candidates_org_qualified", "pentrix_candidates", ["organization_id", "qualified"])
    op.create_index("ix_pentrix_candidates_org_payment", "pentrix_candidates", ["organization_id", "payment_status"])


def downgrade() -> None:
    op.drop_table("pentrix_candidates")
