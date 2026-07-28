"""
Authorization module — FastAPI dependencies.

Every module protects its endpoints with `require_permissions(...)`, e.g.:

    from modules.authorization.dependencies import require_permissions

    @router.post("/leads")
    async def create_lead(
        payload: LeadCreateRequest,
        user: User = Depends(require_permissions("crm.leads.create")),
    ):
        ...

`User.is_superuser` (set on the Authentication module's `User` model)
always bypasses permission checks. Otherwise the user must hold at least
one role granting every requested permission code (AND semantics) unless
`require_all=False` is passed, in which case any one matching code passes
(OR semantics) — useful for "view OR manage" style checks.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.repository import AuthorizationRepository


def require_permissions(*permission_codes: str, require_all: bool = True):
    async def dependency(
        user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if user.is_superuser:
            return user

        repo = AuthorizationRepository(db)
        user_permissions = await repo.get_permission_codes_for_user(user.id)

        if require_all:
            missing = set(permission_codes) - user_permissions
            if missing:
                raise AuthorizationError(
                    f"This action requires the following permission(s): {', '.join(sorted(missing))}"
                )
        else:
            if not user_permissions.intersection(permission_codes):
                raise AuthorizationError(
                    f"This action requires one of the following permission(s): "
                    f"{', '.join(sorted(permission_codes))}"
                )

        return user

    return dependency


def require_role(*role_slugs: str):
    """Coarser-grained alternative to permission checks, for simple role gates."""

    async def dependency(
        user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if user.is_superuser:
            return user

        repo = AuthorizationRepository(db)
        roles = await repo.get_roles_for_user(user.id)
        user_slugs = {role.slug for role in roles}

        if not user_slugs.intersection(role_slugs):
            raise AuthorizationError(
                f"This action requires one of the following role(s): {', '.join(role_slugs)}"
            )

        return user

    return dependency
