"""
Users module — FastAPI dependencies.

`get_current_user_organization_id` is the dependency every future
business module (CRM, Students, Courses, Accounting, ...) will use to
scope its queries to the caller's tenant, e.g.:

    from modules.users.dependencies import get_current_user_organization_id

    @router.get("/leads")
    async def list_leads(
        organization_id: uuid.UUID = Depends(get_current_user_organization_id),
        ...
    ):
        # filter leads WHERE organization_id == organization_id
"""

import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_context import set_audit_organization
from app.core.exceptions import ValidationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.users.repository import UserProfileRepository


async def get_current_user_organization_id(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    repo = UserProfileRepository(db)
    profile = await repo.get_by_user_id(user.id)
    if not profile:
        raise ValidationError(
            "Your account is not yet associated with an organization. Contact your administrator."
        )
    set_audit_organization(profile.organization_id)
    return profile.organization_id
