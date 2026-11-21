"""
Seed for the live (real backend, real browser) Learning end-to-end tests.

Builds, on top of ``scripts.seed_e2e`` (RBAC, the E2E organization and its administrator), a small but complete cohort that exercises the
whole Learning integration with REAL rows -- nothing here is stubbed:

* an internship course (one chapter, one lesson) linked to the internship "Pentrix Cyber Internship";
* two students with LMS access granted (Asha Rao, Meera Iyer: each with a login, a Student record holding the student role, a granted
  selection and a live enrolment) and one selected student without access (Ravi Kumar);
* an independent student enrolled in the same course WITHOUT any internship (Solo Learner), to prove cohort privacy;
* a plain Administrator with a login (the admin site's page guards need real permissions; the seeded Super Admin has none listed);
* an instructor with a login and no role at all (so no global permission of any kind), assigned to the internship for a window that is open.

Idempotent: re-running changes nothing. Reads its database from ``DATABASE_URL``; run from ``apps/api`` as
``python -m scripts.seed_learning_e2e``. Synthetic data only; the passwords are test values for this fixture.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.main import app  # noqa: F401  (loads every model so the mapper sees the whole schema)

from app.core.logging_config import get_logger
from app.core.security import hash_password
from app.db.session import get_db_context
from modules.authentication.models import UserStatus
from modules.authentication.repository import AuthRepository
from modules.authorization.repository import AuthorizationRepository
from modules.courses.chapters.repository import ChapterRepository
from modules.courses.lessons.repository import LessonRepository
from modules.courses.models import Course, CourseType
from modules.employees.repository import EmployeeRepository
from modules.institutions.models import Institution, InstitutionStudent
from modules.lms.enrollment.repository import EnrollmentRepository
from modules.organizations.repository import OrganizationRepository
from modules.our_internships.instructor_models import InternshipInstructor
from modules.our_internships.models import (
    InternshipScope,
    InternshipSelection,
    LmsStatus,
    OurInternship,
    PaymentStatus,
    VerificationStatus,
)
from modules.students.repository import StudentRepository
from modules.trainers.repository import TrainerRepository
from modules.users.repository import UserProfileRepository
from scripts.seed_e2e import E2E_ORG_SLUG
from scripts.seed_e2e import main as seed_base

logger = get_logger(__name__)

PASSWORD = "LearnE2e123!"
INTERNSHIP_TITLE = "Pentrix Cyber Internship"
COURSE_TITLE = "Cloud Security Fundamentals"
STUDENTS = [("Asha Rao", "asha.e2e@example.com", True), ("Meera Iyer", "meera.e2e@example.com", True), ("Ravi Kumar", "ravi.e2e@example.com", False)]
SOLO = ("Solo Learner", "solo.e2e@example.com")
TRAINER = ("Ila Instructor", "ila.e2e@example.com")
# the Super Admin seeded by seed_e2e bypasses permission checks on the server but has no explicit permissions for the admin site's page guards, so
# its screens refuse it ("You don't have access to this page"). The admin tests use a plain Administrator, like a real operator.
ADMIN = ("Ada Administrator", "admin.learning.e2e@example.com")


async def _user(db, org, email: str, name: str):
    auth = AuthRepository(db)
    user = await auth.get_user_by_email(email)
    if user is not None:
        return user
    user = await auth.create_user(email=email, hashed_password=hash_password(PASSWORD), full_name=name)
    user.status = UserStatus.ACTIVE
    user.is_email_verified = True
    await db.flush()
    await UserProfileRepository(db).create(user_id=user.id, organization_id=org.id)
    await db.flush()
    return user


async def _student(db, org, user, name: str, email: str):
    student = await StudentRepository(db).get_by_user_id(user.id)
    if student is None:
        student = await StudentRepository(db).create(org.id, user_id=user.id, full_name=name, course_name="Cyber", enrollment_date=date(2026, 1, 1))
        student.email = email
        await db.flush()
        repo = AuthorizationRepository(db)
        await repo.assign_role(user.id, (await repo.get_role_by_slug("student")).id, None)
        await db.flush()
    return student


async def main() -> None:
    await seed_base()
    async with get_db_context() as db:
        org = await OrganizationRepository(db).get_by_slug(E2E_ORG_SLUG)
        admin_user = await _user(db, org, ADMIN[1], ADMIN[0])
        repo = AuthorizationRepository(db)
        await repo.assign_role(admin_user.id, (await repo.get_role_by_slug("administrator")).id, None)
        await db.flush()

        internship = (await db.execute(select(OurInternship).where(OurInternship.organization_id == org.id, OurInternship.title == INTERNSHIP_TITLE))).scalar_one_or_none()
        if internship is not None:
            logger.info("seed_learning_e2e_already_seeded", internship_id=str(internship.id))
            return

        course = Course(organization_id=org.id, title=COURSE_TITLE, slug="cloud-security-e2e", is_published=True, course_type=CourseType.INTERNSHIP)
        db.add(course)
        await db.flush()
        chapter = await ChapterRepository(db).create(course_id=course.id, title="Getting started", order_index=1)
        await LessonRepository(db).create(chapter_id=chapter.id, title="Threat modelling basics", order_index=1)
        await db.flush()

        institution = Institution(organization_id=org.id, name="Sri Venkateswara College", location="Tirupati", faculty_name="Dr. L")
        db.add(institution)
        await db.flush()
        internship = OurInternship(organization_id=org.id, title=INTERNSHIP_TITLE, scope=InternshipScope.ALL, lms_course_id=course.id)
        db.add(internship)
        await db.flush()

        for name, email, granted in STUDENTS:
            person = InstitutionStudent(organization_id=org.id, institution_id=institution.id, name=name, email=email)
            db.add(person)
            await db.flush()
            selection = InternshipSelection(organization_id=org.id, internship_id=internship.id, student_id=person.id)
            db.add(selection)
            if granted:
                user = await _user(db, org, email, name)
                student = await _student(db, org, user, name, email)
                await EnrollmentRepository(db).create(student_id=student.id, course_id=course.id, enrolled_on=date.today())
                selection.verification_status = VerificationStatus.VERIFIED
                selection.payment_status = PaymentStatus.PAID
                selection.lms_status = LmsStatus.GRANTED
                selection.lms_user_id = user.id
                selection.lms_student_id = student.id
                selection.lms_course_id = course.id
                selection.lms_granted_at = datetime.now(timezone.utc)
            await db.flush()

        solo_user = await _user(db, org, SOLO[1], SOLO[0])
        solo = await _student(db, org, solo_user, SOLO[0], SOLO[1])
        await EnrollmentRepository(db).create(student_id=solo.id, course_id=course.id, enrolled_on=date.today())

        trainer_user = await _user(db, org, TRAINER[1], TRAINER[0])
        employee = await EmployeeRepository(db).create(organization_id=org.id, user_id=trainer_user.id, full_name=TRAINER[0], date_of_joining=date(2024, 1, 1))
        trainer = await TrainerRepository(db).create(organization_id=org.id, employee_id=employee.id)
        await db.flush()
        db.add(InternshipInstructor(
            organization_id=org.id, internship_id=internship.id, trainer_id=trainer.id,
            access_from=datetime.now(timezone.utc) - timedelta(days=1), access_until=datetime.now(timezone.utc) + timedelta(days=60),
        ))
        await db.flush()
        logger.info("seed_learning_e2e_done", internship_id=str(internship.id), course_id=str(course.id))


if __name__ == "__main__":
    asyncio.run(main())
