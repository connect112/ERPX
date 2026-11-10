"""
Which internships a course belongs to, and (for staff who may see finance) what each of them charges.

The only link is ``our_internships.lms_course_id``; nothing here is stored. The fee is read from the internship's own onboarding
settings through the same function that prices a student's offer (``fees.snapshot``), so a course screen can never show an amount the
onboarding would not charge. It is shown only when the internship has saved onboarding settings (a default is not a fee), the fee is
above zero, the course is an internship course set to show it, and the caller holds the finance permission.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.authentication.models import User
from modules.courses.models import Course, CourseType
from modules.our_internships.models import OurInternship


async def linked_internships(db: AsyncSession, organization_id: uuid.UUID, course_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[OurInternship]]:
    """The internships of this organization that use each course, newest first."""
    if not course_ids:
        return {}
    rows = (
        await db.execute(
            select(OurInternship)
            .where(OurInternship.organization_id == organization_id, OurInternship.lms_course_id.in_(course_ids))
            .order_by(OurInternship.created_at.desc())
        )
    ).scalars().all()
    out: dict[uuid.UUID, list[OurInternship]] = {}
    for internship in rows:
        out.setdefault(internship.lms_course_id, []).append(internship)
    return out


async def fee_of(db: AsyncSession, internship: OurInternship) -> dict | None:
    """The internship's fee as onboarding would charge it, or None when there is nothing trustworthy to show."""
    from modules.internship_onboarding import fees as fee_maths
    from modules.internship_onboarding.service import config_of

    record, config = await config_of(db, internship)
    if record is None or config.fees.base_amount <= 0:
        return None
    snap = fee_maths.snapshot(config.fees)
    return {
        "currency": snap["currency"],
        "total": snap["total"],
        "base": snap["base"],
        "discount": snap["discount"],
        "tax_mode": snap["tax_mode"],
        "tax_label": snap["tax_label"],
        "tax": snap["tax"],
    }


async def can_see_internships(db: AsyncSession, user: User) -> bool:
    from modules.internship_onboarding.service import has

    return await has(db, user, "our_internships.view")


async def can_see_fees(db: AsyncSession, user: User) -> bool:
    from modules.internship_onboarding.service import FINANCE_MANAGE, FINANCE_VIEW, has

    return await has(db, user, FINANCE_VIEW) or await has(db, user, FINANCE_MANAGE)


async def describe(db: AsyncSession, user: User, organization_id: uuid.UUID, courses: list[Course]) -> dict[uuid.UUID, list[dict]]:
    """For staff screens: each course's linked internships ({id, title, status, fee}). Empty for a caller who may not see internships;
    the fee is included only under the rules in this module's docstring."""
    if not await can_see_internships(db, user):
        return {c.id: [] for c in courses}
    links = await linked_internships(db, organization_id, [c.id for c in courses])
    show_fees = await can_see_fees(db, user)
    out: dict[uuid.UUID, list[dict]] = {}
    for course in courses:
        items = []
        for internship in links.get(course.id, []):
            fee = None
            if show_fees and course.course_type == CourseType.INTERNSHIP and course.show_internship_fee:
                fee = await fee_of(db, internship)
            items.append({"id": internship.id, "title": internship.title, "status": internship.status.value, "fee": fee})
        out[course.id] = items
    return out


# ------------------------------------------------------------------ what a student may see of the linked course


async def learning_course_for_portal(db: AsyncSession, internship: OurInternship, selection) -> dict | None:
    """The internship's linked course as the onboarding page shows it: its title, description, level and duration, nothing else. No
    price, no content, no link to the lessons: those exist only once LMS access has been granted (``accessible``), and then the link is
    the LMS's own My Courses page."""
    from app.core.config import settings
    from modules.courses.repository import CourseRepository
    from modules.our_internships.models import LmsStatus

    if internship.lms_course_id is None:
        return None
    course = await CourseRepository(db).get_by_id(internship.lms_course_id, internship.organization_id)
    if course is None:
        return None
    granted = selection.lms_status == LmsStatus.GRANTED
    return {
        "title": course.title,
        "description": course.short_description or course.description,
        "level": course.level.value,
        "duration_hours": course.duration_hours,
        "accessible": granted,
        "lms_url": f"{settings.STUDENT_PORTAL_URL.rstrip('/')}/courses/{selection.lms_course_id or course.id}" if granted else None,
    }


async def course_ref_for_student(db: AsyncSession, student, selection, internship: OurInternship) -> dict | None:
    """The course shown on a student's own internship: the one they were enrolled in (so a later relink never changes what they were
    given), else the internship's current one. ``accessible`` is true only while their enrolment is live, which is what the LMS checks."""
    from modules.courses.repository import CourseRepository
    from modules.lms.enrollment.access import LIVE
    from modules.lms.enrollment.repository import EnrollmentRepository

    course_id = selection.lms_course_id or internship.lms_course_id
    if course_id is None:
        return None
    course = await CourseRepository(db).get_by_id(course_id, internship.organization_id)
    if course is None:
        return None
    enrollment = await EnrollmentRepository(db).get_by_student_and_course(student.id, course.id)
    return {
        "id": course.id,
        "title": course.title,
        "level": course.level.value,
        "duration_hours": course.duration_hours,
        "accessible": enrollment is not None and enrollment.status in LIVE,
    }


async def internships_for_enrollments(db: AsyncSession, student, course_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    """For a student's own enrolments: the internships that gave them each course. Only their own internships, only live access."""
    from modules.our_internships.models import InternshipSelection, LmsStatus

    if not course_ids:
        return {}
    rows = (
        await db.execute(
            select(InternshipSelection.lms_course_id, OurInternship.id, OurInternship.title)
            .join(OurInternship, OurInternship.id == InternshipSelection.internship_id)
            .where(
                InternshipSelection.lms_student_id == student.id,
                InternshipSelection.lms_status == LmsStatus.GRANTED,
                InternshipSelection.organization_id == student.organization_id,
                InternshipSelection.lms_course_id.in_(course_ids),
            )
            .order_by(OurInternship.title)
        )
    ).all()
    out: dict[uuid.UUID, list[dict]] = {}
    for course_id, internship_id, title in rows:
        out.setdefault(course_id, []).append({"id": internship_id, "title": title})
    return out
