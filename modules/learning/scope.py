"""Who may reach an internship's own (cohort) activities from a course screen, and what a student may see of them.

An activity that carries an ``internship_id`` (a practical, viva, discussion thread or assessment of ONE internship) is the internship's, not
the course's: the course-level permissions (``lms.*``, ``examinations.*``) never open it. It is reached through Our Internships access
(``our_internships.view`` / ``.manage`` or an active instructor assignment, instructors never deleting) and, for a student, a granted
selection on THAT internship. A record with no ``internship_id`` is course-wide and is governed by the course permissions exactly as before.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from modules.authentication.models import User
from modules.authorization.repository import AuthorizationRepository
from modules.our_internships.access import NO_DELETE, InstructorService, Level, assert_internship_access
from modules.our_internships.models import InternshipSelection, LmsStatus, OurInternship
from modules.students.models import Student


async def has_permission(db: AsyncSession, user: User, code: str) -> bool:
    if user.is_superuser:
        return True
    return code in await AuthorizationRepository(db).get_permission_codes_for_user(user.id)


async def require_permission(db: AsyncSession, user: User, code: str) -> None:
    if not await has_permission(db, user, code):
        raise AuthorizationError(f"This action requires the following permission(s): {code}")


async def internship_of_course(
    db: AsyncSession, organization_id: uuid.UUID, internship_id: uuid.UUID, course_id: uuid.UUID | None
) -> OurInternship:
    """The internship, if it is in this organization and (when given) linked to this course; otherwise "not found"."""
    internship = (
        await db.execute(select(OurInternship).where(OurInternship.id == internship_id, OurInternship.organization_id == organization_id))
    ).scalar_one_or_none()
    if internship is None or (course_id is not None and internship.lms_course_id != course_id):
        raise NotFoundError("Internship", internship_id)
    return internship


async def authorize_internship(
    db: AsyncSession,
    user: User,
    organization_id: uuid.UUID,
    internship_id: uuid.UUID,
    level: Level,
    *,
    course_id: uuid.UUID | None = None,
    deleting: bool = False,
) -> OurInternship:
    """Allow Our Internships access to this one internship (instructors included, never for deleting) and return it."""
    internship = await internship_of_course(db, organization_id, internship_id, course_id)
    await assert_internship_access(db, user, internship_id, level)
    if deleting and not await InstructorService(db).has_global(user, level):
        raise AuthorizationError(NO_DELETE)
    return internship


async def visible_internship_ids(db: AsyncSession, user: User, organization_id: uuid.UUID, course_id: uuid.UUID, level: Level = "view") -> set[uuid.UUID]:
    """The internships linked to this course that this staff member may reach (all of them with the organization-wide permission; for an
    instructor only the ones they instruct right now)."""
    rows = (
        await db.execute(select(OurInternship.id).where(OurInternship.organization_id == organization_id, OurInternship.lms_course_id == course_id))
    ).scalars().all()
    service = InstructorService(db)
    if await service.has_global(user, level):
        return set(rows)
    mine = await service.active_internship_ids(user)
    return {i for i in rows if i in mine}


async def student_internship_ids(db: AsyncSession, student: Student, course_id: uuid.UUID) -> set[uuid.UUID]:
    """The internships through which this student holds LMS access to this course right now (their own granted selections). An
    independent course enrolment gives none."""
    rows = await db.execute(
        select(InternshipSelection.internship_id).where(
            InternshipSelection.lms_student_id == student.id,
            InternshipSelection.lms_course_id == course_id,
            InternshipSelection.lms_status == LmsStatus.GRANTED,
            InternshipSelection.organization_id == student.organization_id,
        )
    )
    return set(rows.scalars().all())


async def student_selection(db: AsyncSession, student: Student, internship_id: uuid.UUID) -> InternshipSelection | None:
    return (
        await db.execute(
            select(InternshipSelection).where(
                InternshipSelection.internship_id == internship_id,
                InternshipSelection.lms_student_id == student.id,
                InternshipSelection.lms_status == LmsStatus.GRANTED,
                InternshipSelection.organization_id == student.organization_id,
            )
        )
    ).scalar_one_or_none()


async def authorize_scoped(
    db: AsyncSession,
    user: User,
    organization_id: uuid.UUID,
    course_id: uuid.UUID,
    row_internship_id: uuid.UUID | None,
    level: Level,
    *,
    manage_code: str,
    view_code: str,
    deleting: bool = False,
) -> None:
    """The one rule for staff touching a course activity: an internship's own record needs Our Internships access to that internship; a
    course-wide record needs the course permission, exactly as before. The course permission never opens an internship's record."""
    if row_internship_id is not None:
        await authorize_internship(db, user, organization_id, row_internship_id, level, course_id=course_id, deleting=deleting)
    else:
        await require_permission(db, user, manage_code if level == "manage" else view_code)


async def selection_access(db: AsyncSession, internship_id: uuid.UUID) -> dict[uuid.UUID, tuple[str, str | None]]:
    """For one internship: LMS student id -> (access status, student name) for granted and revoked selections (history stays visible)."""
    from modules.institutions.models import InstitutionStudent

    rows = await db.execute(
        select(InternshipSelection.lms_student_id, InternshipSelection.lms_status, InstitutionStudent.name)
        .join(InstitutionStudent, InstitutionStudent.id == InternshipSelection.student_id)
        .where(
            InternshipSelection.internship_id == internship_id,
            InternshipSelection.lms_student_id.is_not(None),
            InternshipSelection.lms_status.in_([LmsStatus.GRANTED, LmsStatus.REVOKED]),
        )
    )
    return {sid: (st.value, name) for sid, st, name in rows.all()}
