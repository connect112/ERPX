"""
Authentication module — FastAPI dependencies.

`get_current_user` and `get_current_active_user` are the two dependencies
every other module (CRM, Courses, Accounting, Pentrix, ...) imports to
protect its own endpoints, e.g.:

    from modules.authentication.dependencies import get_current_active_user

    @router.get("/leads")
    async def list_leads(user: User = Depends(get_current_active_user)):
        ...

Role/permission-level checks (e.g. "requires role X") are added by the
Authorization module on top of these two primitives.
"""

import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_context import set_audit_user
from app.core.exceptions import AuthenticationError
from app.core.security import TokenPayloadError, TokenType, decode_token
from app.db.session import get_db
from modules.authentication.models import User, UserStatus
from modules.authentication.repository import AuthRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError("Authentication credentials were not provided.")

    try:
        payload = decode_token(credentials.credentials, TokenType.ACCESS)
    except TokenPayloadError as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc

    repo = AuthRepository(db)
    user = await repo.get_user_by_id(uuid.UUID(payload["sub"]))
    if not user:
        raise AuthenticationError("User account not found.")

    set_audit_user(user.id)
    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if user.status != UserStatus.ACTIVE:
        raise AuthenticationError("This account is not active.")
    return user


async def get_current_superuser(user: User = Depends(get_current_active_user)) -> User:
    if not user.is_superuser:
        from app.core.exceptions import AuthorizationError

        raise AuthorizationError("This action requires superuser privileges.")
    return user
