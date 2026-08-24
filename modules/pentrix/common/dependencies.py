"""
Pentrix module — shared dependencies.

`enforce_own_student_or_staff` closes a specific gap: every pentrix route
that takes a `{student_id}` path parameter is gated by `require_permissions`
alone (e.g. `pentrix.instances.view`, `pentrix.flags.submit`), and those
permission codes are intentionally granted to both staff/admin roles *and*
the `student` role — a student needs them to view their own lab instances,
flag solves, achievements, and certifications. But holding the permission
says nothing about *whose* `student_id` is being requested: without this
check, a student granted `pentrix.instances.view` could pass any other
student's id and read their data.

This dependency resolves whether the caller is themselves a linked student
and, if so, pins the path's `student_id` to their own — raising
`AuthorizationError` (403) otherwise. Staff/admin accounts (not linked to
any `Student` row) are unaffected and continue to rely on
`require_permissions` alone, exactly as before this was added. It does not
touch lab/flag/scoring logic — only who is allowed to read whose results.
"""

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.students.repository import StudentRepository


async def assert_can_access_student(student_id: uuid.UUID, user: User, db: AsyncSession) -> None:
    """Plain (non-Depends) form, for routes where the target `student_id`
    isn't a path parameter — e.g. it's in the request body (`launch_lab`),
    or only known after fetching the resource first (`get_instance`/
    `stop_instance`, keyed by `instance_id`, not `student_id`)."""
    if user.is_superuser:
        return
    own_student = await StudentRepository(db).get_by_user_id(user.id)
    if own_student is not None and own_student.id != student_id:
        raise AuthorizationError("You can only access your own Pentrix data.")


async def enforce_own_student_or_staff(
    student_id: uuid.UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """`Depends()` form, for routes where `student_id` is itself a path parameter."""
    await assert_can_access_student(student_id, user, db)
