"""create pentrix tables (labs, instances, challenges, flags, hints, achievements, certifications)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

lab_difficulty_enum = postgresql.ENUM("easy", "medium", "hard", "insane", name="lab_difficulty")
lab_instance_status_enum = postgresql.ENUM(
    "provisioning", "running", "stopped", "expired", "failed", name="lab_instance_status"
)
achievement_criteria_type_enum = postgresql.ENUM(
    "challenges_solved", "points_threshold", name="achievement_criteria_type"
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
    for enum_type in (lab_difficulty_enum, lab_instance_status_enum, achievement_criteria_type_enum):
        enum_type.create(op.get_bind(), checkfirst=True)

    # ---- Labs ----
    op.create_table(
        "pentrix_labs",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("difficulty", postgresql.ENUM("easy", "medium", "hard", "insane", name="lab_difficulty", create_type=False), nullable=False, server_default="easy"),
        sa.Column("environment_image", sa.String(length=255), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("default_duration_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "slug", name="uq_lab_org_slug"),
    )
    op.create_index("ix_pentrix_labs_organization_id", "pentrix_labs", ["organization_id"])
    op.create_index("ix_pentrix_labs_category", "pentrix_labs", ["category"])

    # ---- Lab Instances ----
    op.create_table(
        "pentrix_lab_instances",
        *_tc(),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pentrix_labs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("environment_ref", sa.String(length=255), nullable=True),
        sa.Column("access_endpoint", sa.String(length=512), nullable=True),
        sa.Column("status", postgresql.ENUM("provisioning", "running", "stopped", "expired", "failed", name="lab_instance_status", create_type=False), nullable=False, server_default="provisioning"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pentrix_lab_instances_lab_id", "pentrix_lab_instances", ["lab_id"])
    op.create_index("ix_pentrix_lab_instances_student_id", "pentrix_lab_instances", ["student_id"])
    op.create_index("ix_pentrix_lab_instances_status", "pentrix_lab_instances", ["status"])

    # ---- Challenges ----
    op.create_table(
        "pentrix_challenges",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pentrix_labs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("difficulty", postgresql.ENUM("easy", "medium", "hard", "insane", name="lab_difficulty", create_type=False), nullable=False, server_default="easy"),
        sa.Column("points", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_pentrix_challenges_organization_id", "pentrix_challenges", ["organization_id"])
    op.create_index("ix_pentrix_challenges_lab_id", "pentrix_challenges", ["lab_id"])
    op.create_index("ix_pentrix_challenges_category", "pentrix_challenges", ["category"])

    # ---- Flags & Submissions ----
    op.create_table(
        "pentrix_flags",
        *_tc(),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pentrix_challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flag_hash", sa.String(length=64), nullable=False),
        sa.UniqueConstraint("challenge_id", name="uq_pentrix_flags_challenge_id"),
    )
    op.create_index("ix_pentrix_flags_challenge_id", "pentrix_flags", ["challenge_id"])

    op.create_table(
        "pentrix_submissions",
        *_tc(),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pentrix_challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("points_awarded", sa.Integer(), nullable=False),
        sa.Column("solved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("challenge_id", "student_id", name="uq_submission_challenge_student"),
    )
    op.create_index("ix_pentrix_submissions_challenge_id", "pentrix_submissions", ["challenge_id"])
    op.create_index("ix_pentrix_submissions_student_id", "pentrix_submissions", ["student_id"])

    # ---- Hints ----
    op.create_table(
        "pentrix_hints",
        *_tc(),
        sa.Column("challenge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pentrix_challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hint_text", sa.Text(), nullable=False),
        sa.Column("point_cost", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("order_index", sa.Integer(), nullable=False),
    )
    op.create_index("ix_pentrix_hints_challenge_id", "pentrix_hints", ["challenge_id"])

    op.create_table(
        "pentrix_hint_unlocks",
        *_tc(),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pentrix_hints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "hint_id", name="uq_hint_unlock"),
    )
    op.create_index("ix_pentrix_hint_unlocks_student_id", "pentrix_hint_unlocks", ["student_id"])
    op.create_index("ix_pentrix_hint_unlocks_hint_id", "pentrix_hint_unlocks", ["hint_id"])

    # ---- Achievements ----
    op.create_table(
        "pentrix_achievements",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("criteria_type", postgresql.ENUM("challenges_solved", "points_threshold", name="achievement_criteria_type", create_type=False), nullable=False),
        sa.Column("criteria_value", sa.Integer(), nullable=False),
    )
    op.create_index("ix_pentrix_achievements_organization_id", "pentrix_achievements", ["organization_id"])

    op.create_table(
        "pentrix_student_achievements",
        *_tc(),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("achievement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pentrix_achievements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("awarded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "achievement_id", name="uq_student_achievement"),
    )
    op.create_index("ix_pentrix_student_achievements_student_id", "pentrix_student_achievements", ["student_id"])
    op.create_index("ix_pentrix_student_achievements_achievement_id", "pentrix_student_achievements", ["achievement_id"])

    # ---- Certifications ----
    op.create_table(
        "pentrix_certifications",
        *_tc(),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("track_name", sa.String(length=255), nullable=False),
        sa.Column("certificate_number", sa.String(length=50), nullable=False),
        sa.Column("points_at_issuance", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "track_name", name="uq_pentrix_cert_student_track"),
        sa.UniqueConstraint("certificate_number", name="uq_pentrix_cert_number"),
    )
    op.create_index("ix_pentrix_certifications_student_id", "pentrix_certifications", ["student_id"])
    op.create_index("ix_pentrix_certifications_certificate_number", "pentrix_certifications", ["certificate_number"])


def downgrade() -> None:
    op.drop_table("pentrix_certifications")
    op.drop_table("pentrix_student_achievements")
    op.drop_table("pentrix_achievements")
    op.drop_table("pentrix_hint_unlocks")
    op.drop_table("pentrix_hints")
    op.drop_table("pentrix_submissions")
    op.drop_table("pentrix_flags")
    op.drop_table("pentrix_challenges")
    op.drop_table("pentrix_lab_instances")
    op.drop_table("pentrix_labs")
    for enum_type in (achievement_criteria_type_enum, lab_instance_status_enum, lab_difficulty_enum):
        enum_type.drop(op.get_bind(), checkfirst=True)
