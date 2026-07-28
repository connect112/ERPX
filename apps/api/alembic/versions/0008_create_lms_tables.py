"""create lms tables (enrollment, progress, assignments, assessments, certificates, announcements, discussions, badges)

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

enrollment_status_enum = postgresql.ENUM("active", "completed", "dropped", name="enrollment_status")
submission_status_enum = postgresql.ENUM("submitted", "graded", "late", name="submission_status")
assessment_type_enum = postgresql.ENUM("quiz", "mock_test", "coding_test", name="assessment_type")
attempt_status_enum = postgresql.ENUM("in_progress", "submitted", "evaluated", name="attempt_status")


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
    for enum_type in (
        enrollment_status_enum, submission_status_enum, assessment_type_enum, attempt_status_enum,
    ):
        enum_type.create(op.get_bind(), checkfirst=True)

    # ---- Enrollment ----
    op.create_table(
        "lms_enrollments",
        *_tc(),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrolled_on", sa.Date(), nullable=False),
        sa.Column("status", postgresql.ENUM("active", "completed", "dropped", name="enrollment_status", create_type=False), nullable=False, server_default="active"),
        sa.UniqueConstraint("student_id", "course_id", name="uq_enrollment_student_course"),
    )
    op.create_index("ix_lms_enrollments_student_id", "lms_enrollments", ["student_id"])
    op.create_index("ix_lms_enrollments_course_id", "lms_enrollments", ["course_id"])

    # ---- Progress ----
    op.create_table(
        "lms_lesson_progress",
        *_tc(),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "lesson_id", name="uq_progress_student_lesson"),
    )
    op.create_index("ix_lms_lesson_progress_student_id", "lms_lesson_progress", ["student_id"])
    op.create_index("ix_lms_lesson_progress_lesson_id", "lms_lesson_progress", ["lesson_id"])

    # ---- Assignments ----
    op.create_table(
        "lms_assignments",
        *_tc(),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=False, server_default="100"),
    )
    op.create_index("ix_lms_assignments_course_id", "lms_assignments", ["course_id"])

    op.create_table(
        "lms_assignment_submissions",
        *_tc(),
        sa.Column("assignment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lms_assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_url", sa.String(length=512), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", postgresql.ENUM("submitted", "graded", "late", name="submission_status", create_type=False), nullable=False, server_default="submitted"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.UniqueConstraint("assignment_id", "student_id", name="uq_submission_assignment_student"),
    )
    op.create_index("ix_lms_assignment_submissions_assignment_id", "lms_assignment_submissions", ["assignment_id"])
    op.create_index("ix_lms_assignment_submissions_student_id", "lms_assignment_submissions", ["student_id"])

    # ---- Assessments ----
    op.create_table(
        "lms_assessments",
        *_tc(),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("assessment_type", postgresql.ENUM("quiz", "mock_test", "coding_test", name="assessment_type", create_type=False), nullable=False, server_default="quiz"),
        sa.Column("total_marks", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("passing_marks", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_lms_assessments_course_id", "lms_assessments", ["course_id"])

    op.create_table(
        "lms_assessment_attempts",
        *_tc(),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lms_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("status", postgresql.ENUM("in_progress", "submitted", "evaluated", name="attempt_status", create_type=False), nullable=False, server_default="in_progress"),
        sa.UniqueConstraint("assessment_id", "student_id", name="uq_attempt_assessment_student"),
    )
    op.create_index("ix_lms_assessment_attempts_assessment_id", "lms_assessment_attempts", ["assessment_id"])
    op.create_index("ix_lms_assessment_attempts_student_id", "lms_assessment_attempts", ["student_id"])

    # ---- Certificates ----
    op.create_table(
        "lms_certificates",
        *_tc(),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("certificate_number", sa.String(length=50), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "course_id", name="uq_certificate_student_course"),
        sa.UniqueConstraint("certificate_number", name="uq_certificate_number"),
    )
    op.create_index("ix_lms_certificates_student_id", "lms_certificates", ["student_id"])
    op.create_index("ix_lms_certificates_course_id", "lms_certificates", ["course_id"])
    op.create_index("ix_lms_certificates_certificate_number", "lms_certificates", ["certificate_number"])

    # ---- Announcements ----
    op.create_table(
        "lms_announcements",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lms_announcements_organization_id", "lms_announcements", ["organization_id"])
    op.create_index("ix_lms_announcements_course_id", "lms_announcements", ["course_id"])

    # ---- Discussions ----
    op.create_table(
        "lms_discussion_threads",
        *_tc(),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_lms_discussion_threads_course_id", "lms_discussion_threads", ["course_id"])

    op.create_table(
        "lms_discussion_replies",
        *_tc(),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lms_discussion_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
    )
    op.create_index("ix_lms_discussion_replies_thread_id", "lms_discussion_replies", ["thread_id"])

    # ---- Badges ----
    op.create_table(
        "lms_badges",
        *_tc(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon_url", sa.String(length=512), nullable=True),
    )
    op.create_index("ix_lms_badges_organization_id", "lms_badges", ["organization_id"])

    op.create_table(
        "lms_student_badges",
        *_tc(),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("badge_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lms_badges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("awarded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "badge_id", name="uq_student_badge"),
    )
    op.create_index("ix_lms_student_badges_student_id", "lms_student_badges", ["student_id"])
    op.create_index("ix_lms_student_badges_badge_id", "lms_student_badges", ["badge_id"])


def downgrade() -> None:
    op.drop_table("lms_student_badges")
    op.drop_table("lms_badges")
    op.drop_table("lms_discussion_replies")
    op.drop_table("lms_discussion_threads")
    op.drop_table("lms_announcements")
    op.drop_table("lms_certificates")
    op.drop_table("lms_assessment_attempts")
    op.drop_table("lms_assessments")
    op.drop_table("lms_assignment_submissions")
    op.drop_table("lms_assignments")
    op.drop_table("lms_lesson_progress")
    op.drop_table("lms_enrollments")
    for enum_type in (
        attempt_status_enum, assessment_type_enum, submission_status_enum, enrollment_status_enum,
    ):
        enum_type.drop(op.get_bind(), checkfirst=True)
