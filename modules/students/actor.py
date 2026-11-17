"""Whose work is it? A student acts only as themselves; staff who hold the matching permission may act for a student of their organization.

Several activity endpoints (assessment attempts, assignment submissions, exam attempts) used to take ``student_id`` from the request, so any
caller holding the "attempt" or "submit" permission (the Student role does) could act as any student they knew an id for. These helpers
make the caller's own student record the only one a student-linked, non-staff caller can use, and keep staff grading and recording working.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from modules.authentication.models import User
from modules.authorization.repository import AuthorizationRepository
from modules.students.models import Student
from modules.students.repository import StudentRepository

NOT_YOURS = "You can only do this for yourself."


async def _is_staff(db: AsyncSession, user: User, staff_permissions: set[str]) -> bool:
    if user.is_superuser:
        return True
    codes = await AuthorizationRepository(db).get_permission_codes_for_user(user.id)
    return bool(staff_permissions & set(codes))


async def resolve_actor(
    db: AsyncSession, user: User, organization_id: uuid.UUID, requested_student_id: uuid.UUID | None, staff_permissions: set[str]
) -> Student:
    """The student this request is for. A student-linked caller without a staff permission is always themselves (naming someone else is
    refused). Staff name the student; that student must belong to the caller's organization."""
    own = await StudentRepository(db).get_by_user_id(user.id)
    if own is not None and not await _is_staff(db, user, staff_permissions):
        if requested_student_id is not None and requested_student_id != own.id:
            raise AuthorizationError(NOT_YOURS)
        return own
    if requested_student_id is None:
        raise ValidationError("student_id is required.")
    student = await StudentRepository(db).get_by_id(requested_student_id, organization_id)
    if student is None:
        raise NotFoundError("Student", requested_student_id)
    return student


async def ensure_own_or_staff(db: AsyncSession, user: User, student_id: uuid.UUID, staff_permissions: set[str]) -> None:
    """For something that already belongs to ``student_id`` (an attempt, an answer): only that student, or staff, may touch it."""
    own = await StudentRepository(db).get_by_user_id(user.id)
    if own is not None and own.id != student_id and not await _is_staff(db, user, staff_permissions):
        raise AuthorizationError(NOT_YOURS)
    if own is None and not await _is_staff(db, user, staff_permissions):
        raise AuthorizationError(NOT_YOURS)
