"""hackathon participants: who was invited to which hackathon

Revision ID: 0054
Revises: 0053
Create Date: 2026-10-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0054"
down_revision: Union[str, None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hackathon_participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "hackathon_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hackathons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("hackathon_id", "student_id", name="uq_hackathon_participant"),
    )
    op.create_index("ix_hackathon_participants_hackathon_id", "hackathon_participants", ["hackathon_id"])
    op.create_index("ix_hackathon_participants_student_id", "hackathon_participants", ["student_id"])

    # Fill in who is already taking part: everyone in a team, and everyone who was bulk-created for
    # a hackathon (their student record carries the hackathon's title and they hold the participant role).
    op.execute(
        """
        INSERT INTO hackathon_participants (hackathon_id, student_id)
        SELECT DISTINCT t.hackathon_id, tm.student_id
        FROM hackathon_team_members tm
        JOIN hackathon_teams t ON t.id = tm.team_id
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO hackathon_participants (hackathon_id, student_id)
        SELECT DISTINCT h.id, s.id
        FROM students s
        JOIN hackathons h ON h.title = s.course_name AND h.organization_id = s.organization_id
        JOIN user_roles ur ON ur.user_id = s.user_id
        JOIN roles r ON r.id = ur.role_id AND r.slug = 'hackathon_participant'
        WHERE s.deleted_at IS NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_hackathon_participants_student_id", table_name="hackathon_participants")
    op.drop_index("ix_hackathon_participants_hackathon_id", table_name="hackathon_participants")
    op.drop_table("hackathon_participants")
