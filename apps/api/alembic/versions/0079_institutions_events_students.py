"""institutions, their events and registered students; exams and hackathons can belong to an event

Revision ID: 0079
Revises: 0078
Create Date: 2026-10-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0079"
down_revision: Union[str, None] = "0078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)


def _id_and_timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "institutions",
        *_id_and_timestamps(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("mou_details", sa.Text(), nullable=True),
        sa.Column("mou_filename", sa.String(255), nullable=True),
        sa.Column("mou_content_type", sa.String(100), nullable=True),
        sa.Column("mou_size_bytes", sa.Integer(), nullable=True),
        sa.Column("mou_data", sa.LargeBinary(), nullable=True),
        sa.Column("faculty_name", sa.String(255), nullable=False),
        sa.Column("faculty_designation", sa.String(255), nullable=True),
        sa.Column("faculty_email", sa.String(255), nullable=True),
        sa.Column("faculty_phone", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_institutions_organization_id", "institutions", ["organization_id"])

    event_type = postgresql.ENUM("workshop", "hackathon", "exam", "other", name="institution_event_type")
    event_status = postgresql.ENUM("upcoming", "ongoing", "completed", name="institution_event_status")
    event_type.create(op.get_bind(), checkfirst=True)
    event_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "institution_events",
        *_id_and_timestamps(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institution_id", _UUID, sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", _UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM(name="institution_event_type", create_type=False),
            server_default="workshop",
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("max_capacity", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="institution_event_status", create_type=False),
            server_default="upcoming",
            nullable=False,
        ),
    )
    op.create_index("ix_institution_events_organization_id", "institution_events", ["organization_id"])
    op.create_index("ix_institution_events_institution_id", "institution_events", ["institution_id"])
    op.create_index("ix_institution_events_status", "institution_events", ["status"])

    op.create_table(
        "institution_students",
        *_id_and_timestamps(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("institution_id", _UUID, sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("details", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.UniqueConstraint("institution_id", "email", name="uq_institution_student_email"),
    )
    op.create_index("ix_institution_students_organization_id", "institution_students", ["organization_id"])
    op.create_index("ix_institution_students_institution_id", "institution_students", ["institution_id"])
    op.create_index("ix_institution_students_email", "institution_students", ["email"])

    op.create_table(
        "institution_event_students",
        *_id_and_timestamps(),
        sa.Column("organization_id", _UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", _UUID, sa.ForeignKey("institution_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", _UUID, sa.ForeignKey("institution_students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("individual_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.UniqueConstraint("event_id", "student_id", name="uq_event_registration"),
    )
    op.create_index("ix_institution_event_students_organization_id", "institution_event_students", ["organization_id"])
    op.create_index("ix_institution_event_students_event_id", "institution_event_students", ["event_id"])
    op.create_index("ix_institution_event_students_student_id", "institution_event_students", ["student_id"])

    # An exam or a hackathon can belong to an event. Nullable: nothing existing is touched, and deleting an event leaves
    # the exam or hackathon in place (just no longer linked).
    for table in ("workshop_exams", "hackathons"):
        op.add_column(
            table, sa.Column("event_id", _UUID, sa.ForeignKey("institution_events.id", ondelete="SET NULL"), nullable=True)
        )
        op.create_index(f"ix_{table}_event_id", table, ["event_id"])


def downgrade() -> None:
    for table in ("hackathons", "workshop_exams"):
        op.drop_index(f"ix_{table}_event_id", table_name=table)
        op.drop_column(table, "event_id")
    op.drop_table("institution_event_students")
    op.drop_table("institution_students")
    op.drop_table("institution_events")
    op.drop_table("institutions")
    postgresql.ENUM(name="institution_event_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="institution_event_type").drop(op.get_bind(), checkfirst=True)
