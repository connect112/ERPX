"""Reading a course's curriculum from an internship screen.

Editing the curriculum always needs ``courses.manage``: managing an internship's activities never gives it. Reading it is also open to
staff who may view an internship linked to the course (an instructor on that internship during their window, or Our Internships viewers),
so the internship's Learning workspace can show the same chapters, lessons and resources without handing out course-wide permissions.
"""

import uuid

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.learning.scope import has_permission, visible_internship_ids
from modules.users.dependencies import get_current_user_organization_id


async def course_read_access(
    request: Request,
    user: User = Depends(get_current_active_user),
    organization_id: uuid.UUID = Depends(get_current_user_organization_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    if await has_permission(db, user, "courses.view"):
        return user
    raw = request.path_params.get("course_id")
    try:
        course_id = uuid.UUID(str(raw))
    except ValueError:
        course_id = None
    if course_id is not None and await visible_internship_ids(db, user, organization_id, course_id, "view"):
        return user
    raise AuthorizationError("This action requires the following permission(s): courses.view")
