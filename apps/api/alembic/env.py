"""
Alembic environment script.

Runs migrations in 'online' async mode against the same DATABASE_URL the
application uses. As each module is built, its `models.py` is imported
below so that `Base.metadata` (and therefore autogenerate) sees every
table across the entire platform — CRM, courses, accounting, pentrix,
everything — from a single source of truth.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.db.session import Base

# Import every module's ORM models here as they are built, so Alembic's
# autogenerate can see the full schema.
from modules.authentication.models import (  # noqa: E402,F401
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    User,
)
from modules.authorization.models import (  # noqa: E402,F401
    Permission,
    Role,
    RolePermission,
    UserRole,
)
from modules.organizations.models import Organization  # noqa: E402,F401
from modules.branches.models import Branch  # noqa: E402,F401
from modules.users.models import UserProfile  # noqa: E402,F401
from modules.settings.models import OrganizationSetting  # noqa: E402,F401
from modules.crm.leads.models import Lead  # noqa: E402,F401
from modules.crm.enquiries.models import Enquiry  # noqa: E402,F401
from modules.crm.followups.models import FollowUp  # noqa: E402,F401
from modules.crm.counselling.models import CounsellingSession  # noqa: E402,F401
from modules.crm.admissions.models import Admission  # noqa: E402,F401
from modules.students.models import Student  # noqa: E402,F401
from modules.courses.categories.models import Category  # noqa: E402,F401
from modules.courses.models import Course  # noqa: E402,F401
from modules.courses.chapters.models import Chapter  # noqa: E402,F401
from modules.courses.lessons.models import Lesson  # noqa: E402,F401
from modules.courses.resources.models import Resource  # noqa: E402,F401
from modules.courses.learning_paths.models import LearningPath, LearningPathCourse  # noqa: E402,F401
from modules.lms.enrollment.models import Enrollment  # noqa: E402,F401
from modules.lms.progress.models import LessonProgress  # noqa: E402,F401
from modules.lms.assignments.models import Assignment, AssignmentSubmission  # noqa: E402,F401
from modules.lms.assessments.models import Assessment, AssessmentAttempt  # noqa: E402,F401
from modules.lms.certificates.models import Certificate  # noqa: E402,F401
from modules.lms.announcements.models import Announcement  # noqa: E402,F401
from modules.lms.discussions.models import DiscussionThread, DiscussionReply  # noqa: E402,F401
from modules.lms.badges.models import Badge, StudentBadge  # noqa: E402,F401
from modules.examinations.question_bank.models import Question  # noqa: E402,F401
from modules.examinations.exams.models import Exam, ExamQuestion  # noqa: E402,F401
from modules.examinations.evaluation.models import ExamAttempt, ExamAnswer  # noqa: E402,F401
from modules.examinations.practicals.models import PracticalExam, PracticalResult  # noqa: E402,F401
from modules.examinations.viva.models import VivaExam, VivaResult  # noqa: E402,F401
from modules.pentrix.labs.models import Lab  # noqa: E402,F401
from modules.pentrix.lab_instances.models import LabInstance  # noqa: E402,F401
from modules.pentrix.challenges.models import Challenge  # noqa: E402,F401
from modules.pentrix.flags.models import Flag, Submission  # noqa: E402,F401
from modules.pentrix.hints.models import Hint, HintUnlock  # noqa: E402,F401
from modules.pentrix.achievements.models import Achievement, StudentAchievement  # noqa: E402,F401
from modules.pentrix.certifications.models import PentrixCertification  # noqa: E402,F401
from modules.audit.models import AuditLog  # noqa: E402,F401
from modules.documents.models import Document  # noqa: E402,F401
from modules.trainers.models import Trainer  # noqa: E402,F401
from modules.classrooms.models import Classroom  # noqa: E402,F401
from modules.batches.models import Batch  # noqa: E402,F401
from modules.timetable.models import TimetableEntry  # noqa: E402,F401
from modules.live_classes.models import LiveClass  # noqa: E402,F401
from modules.workshops.models import Workshop, WorkshopRegistration  # noqa: E402,F401
from modules.hackathons.models import Hackathon, Team, TeamMember, Submission  # noqa: E402,F401
from modules.placements.models import Company, JobPosting, Application  # noqa: E402,F401
from modules.internships.models import InternshipPosting, InternshipApplication, Internship  # noqa: E402,F401
from modules.alumni.models import AlumniProfile, AlumniEvent, EventRegistration, JobReferral  # noqa: E402,F401
from modules.media.models import Album, MediaAsset  # noqa: E402,F401
from modules.workflow.models import ApprovalWorkflow, ApprovalStep, ApprovalRequest, ApprovalAction  # noqa: E402,F401
from modules.notifications.models import Notification  # noqa: E402,F401
from modules.communication.models import CommunicationLog  # noqa: E402,F401
from modules.events.models import Event  # noqa: E402,F401
from modules.backups.models import BackupJob  # noqa: E402,F401
from modules.integrations.models import Integration  # noqa: E402,F401

# Additional modules are imported below as they are built, e.g.:
#   from modules.accounting.models import *          # noqa

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
