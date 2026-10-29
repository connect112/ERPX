"""pentrix operations: bookings mirror, reminders, sync state

Revision ID: 0091
Revises: 0090
Create Date: 2026-10-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0091"
down_revision: Union[str, None] = "0090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _base(*extra):
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        *extra,
    ]


def upgrade() -> None:
    op.create_table(
        "pentrix_bookings",
        *_base(
            sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("pentrix_booking_id", sa.String(36), nullable=False),
            sa.Column("reference", sa.String(16)),
            sa.Column("pentrix_user_id", sa.String(36), nullable=False),
            sa.Column("candidate_name", sa.String(255), nullable=False, server_default=""),
            sa.Column("candidate_email", sa.String(255), nullable=False, server_default=""),
            sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("slot_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("assigned_staff_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("assigned_staff_name", sa.String(255)),
            sa.Column("meeting_url", sa.String(512)),
            sa.Column("notes", sa.Text()),
            sa.Column("reschedule_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cancelled_by", sa.String(16)),
            sa.Column("source_created_at", sa.DateTime(timezone=True)),
            sa.Column("source_updated_at", sa.DateTime(timezone=True)),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("pentrix_booking_id", name="uq_pentrix_bookings_pentrix_booking_id"),
        ),
    )
    op.create_index("ix_pentrix_bookings_organization_id", "pentrix_bookings", ["organization_id"])
    op.create_index("ix_pentrix_bookings_reference", "pentrix_bookings", ["reference"])
    op.create_index("ix_pentrix_bookings_pentrix_user_id", "pentrix_bookings", ["pentrix_user_id"])
    op.create_index("ix_pentrix_bookings_status", "pentrix_bookings", ["status"])
    op.create_index("ix_pentrix_bookings_org_slot", "pentrix_bookings", ["organization_id", "slot_start"])
    op.create_index("ix_pentrix_bookings_staff_slot", "pentrix_bookings", ["assigned_staff_user_id", "slot_start"])

    op.create_table(
        "pentrix_booking_reminders",
        *_base(
            sa.Column("booking_id", _UUID, sa.ForeignKey("pentrix_bookings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(8), nullable=False),
            sa.Column("audience", sa.String(10), nullable=False),
            sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("recipient", sa.String(255), nullable=False),
            sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error", sa.String(500)),
            sa.Column("sent_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("booking_id", "kind", "audience", "slot_start", name="uq_pentrix_reminder"),
        ),
    )
    op.create_index("ix_pentrix_booking_reminders_booking_id", "pentrix_booking_reminders", ["booking_id"])

    op.create_table(
        "pentrix_sync_state",
        *_base(
            sa.Column("key", sa.String(60), nullable=False),
            sa.Column("value", sa.Text(), nullable=False, server_default=""),
            sa.Column("last_run_at", sa.DateTime(timezone=True)),
            sa.Column("last_error", sa.String(500)),
            sa.UniqueConstraint("key", name="uq_pentrix_sync_state_key"),
        ),
    )


def downgrade() -> None:
    op.drop_table("pentrix_sync_state")
    op.drop_table("pentrix_booking_reminders")
    op.drop_table("pentrix_bookings")
