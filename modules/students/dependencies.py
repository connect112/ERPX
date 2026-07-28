"""
Students module — FastAPI dependencies.

`get_current_student` is what every self-service "me" endpoint (student
portal: my enrollments, my progress, my assignments, ...) depends on
instead of an RBAC permission check — a student doesn't need
`lms.enrollment.view` to see their *own* enrollments; owning the record
is the authorization. Staff/admin endpoints viewing arbitrary students'
data continue to use `require_permissions(...)` exactly as before, this
is additive, not a replacement.
"""

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.students.models import Student
from modules.students.repository import StudentRepository


async def get_current_student(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Student:
    repo = StudentRepository(db)
    student = await repo.get_by_user_id(user.id)
    if not student:
        raise ValidationError(
            "Your account is not linked to a student record. Contact your administrator."
        )
    return student


async def get_current_student_organization_id(
    student: Student = Depends(get_current_student),
) -> uuid.UUID:
    return student.organization_id
