"""create courses tables (categories, courses, chapters, lessons, resources, learning paths)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

course_level_enum = postgresql.ENUM("beginner", "intermediate", "advanced", name="course_level")
lesson_content_type_enum = postgresql.ENUM(
    "video", "text", "document", "quiz", name="lesson_content_type"
)
resource_type_enum = postgresql.ENUM(
    "video", "note", "pdf", "document", "link", "other", name="resource_type"
)


def _timestamp_columns():
    return [
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    for enum_type in (course_level_enum, lesson_content_type_enum, resource_type_enum):
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "course_categories",
        *_timestamp_columns(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "slug", name="uq_category_org_slug"),
    )
    op.create_index("ix_course_categories_organization_id", "course_categories", ["organization_id"])

    op.create_table(
        "courses",
        *_timestamp_columns(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("course_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("short_description", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=512), nullable=True),
        sa.Column("level", postgresql.ENUM(
            "beginner", "intermediate", "advanced", name="course_level", create_type=False,
        ), nullable=False, server_default="beginner"),
        sa.Column("duration_hours", sa.Integer(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("organization_id", "slug", name="uq_course_org_slug"),
    )
    op.create_index("ix_courses_organization_id", "courses", ["organization_id"])
    op.create_index("ix_courses_category_id", "courses", ["category_id"])

    op.create_table(
        "course_chapters",
        *_timestamp_columns(),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.UniqueConstraint("course_id", "order_index", name="uq_chapter_course_order"),
    )
    op.create_index("ix_course_chapters_course_id", "course_chapters", ["course_id"])

    op.create_table(
        "course_lessons",
        *_timestamp_columns(),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("course_chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_type", postgresql.ENUM(
            "video", "text", "document", "quiz", name="lesson_content_type", create_type=False,
        ), nullable=False, server_default="video"),
        sa.Column("video_url", sa.String(length=512), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_preview", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("chapter_id", "order_index", name="uq_lesson_chapter_order"),
    )
    op.create_index("ix_course_lessons_chapter_id", "course_lessons", ["chapter_id"])

    op.create_table(
        "course_resources",
        *_timestamp_columns(),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("course_lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("resource_type", postgresql.ENUM(
            "video", "note", "pdf", "document", "link", "other", name="resource_type", create_type=False,
        ), nullable=False, server_default="other"),
        sa.Column("file_url", sa.String(length=512), nullable=False),
        sa.Column("is_downloadable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_course_resources_lesson_id", "course_resources", ["lesson_id"])

    op.create_table(
        "course_learning_paths",
        *_timestamp_columns(),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("organization_id", "slug", name="uq_learning_path_org_slug"),
    )
    op.create_index("ix_course_learning_paths_organization_id", "course_learning_paths", ["organization_id"])

    op.create_table(
        "course_learning_path_courses",
        *_timestamp_columns(),
        sa.Column("learning_path_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("course_learning_paths.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.UniqueConstraint("learning_path_id", "course_id", name="uq_learning_path_course"),
        sa.UniqueConstraint("learning_path_id", "order_index", name="uq_learning_path_order"),
    )
    op.create_index("ix_course_learning_path_courses_learning_path_id", "course_learning_path_courses", ["learning_path_id"])
    op.create_index("ix_course_learning_path_courses_course_id", "course_learning_path_courses", ["course_id"])


def downgrade() -> None:
    op.drop_table("course_learning_path_courses")
    op.drop_table("course_learning_paths")
    op.drop_table("course_resources")
    op.drop_table("course_lessons")
    op.drop_table("course_chapters")
    op.drop_table("courses")
    op.drop_table("course_categories")
    for enum_type in (resource_type_enum, lesson_content_type_enum, course_level_enum):
        enum_type.drop(op.get_bind(), checkfirst=True)
