"""
Authorization module — routes.

Registered under /api/v1/authorization in app/api/v1/router.py.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authorization.dependencies import require_permissions
from modules.authorization.schemas import (
    AssignPermissionsRequest,
    AssignRoleRequest,
    MessageResponse,
    PermissionPublic,
    RoleCreateRequest,
    RolePublic,
    RoleUpdateRequest,
    RoleWithPermissions,
    UserRolesResponse,
)
from modules.authorization.service import AuthorizationService

router = APIRouter()


@router.get("/me", response_model=UserRolesResponse)
async def get_my_roles(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """The caller's own roles + effective permission codes — no permission
    required, since a token holder reading their own grants is exactly the
    ownership-is-the-authorization pattern this codebase already uses for
    `/me` endpoints elsewhere (see modules/students/dependencies.py). Client
    apps (e.g. apps/student-portal) fetch this once on login to drive which
    nav items and routes render, so a role's actual grant set is always the
    single source of truth for what the UI ever shows — never hardcoded."""
    service = AuthorizationService(db)
    result = await service.get_user_roles_and_permissions(user.id)
    return UserRolesResponse(
        user_id=user.id,
        roles=[RolePublic.model_validate(r) for r in result["roles"]],
        effective_permissions=result["effective_permissions"],
    )


@router.get("/permissions", response_model=list[PermissionPublic])
async def list_permissions(
    user: User = Depends(require_permissions("authorization.roles.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AuthorizationService(db)
    permissions = await service.list_permissions()
    return [PermissionPublic.model_validate(p) for p in permissions]


@router.get("/roles", response_model=list[RolePublic])
async def list_roles(
    user: User = Depends(require_permissions("authorization.roles.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AuthorizationService(db)
    roles = await service.list_roles()
    return [RolePublic.model_validate(r) for r in roles]


@router.post("/roles", response_model=RolePublic, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreateRequest,
    user: User = Depends(require_permissions("authorization.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AuthorizationService(db)
    role = await service.create_role(payload.name, payload.slug, payload.description)
    return RolePublic.model_validate(role)


@router.get("/roles/{role_id}", response_model=RoleWithPermissions)
async def get_role(
    role_id: uuid.UUID,
    user: User = Depends(require_permissions("authorization.roles.view")),
    db: AsyncSession = Depends(get_db),
):
    service = AuthorizationService(db)
    role = await service.get_role_with_permissions(role_id)
    return RoleWithPermissions(
        **RolePublic.model_validate(role).model_dump(),
        permissions=[PermissionPublic.model_validate(rp.permission) for rp in role.role_permissions],
    )


@router.patch("/roles/{role_id}", response_model=RolePublic)
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdateRequest,
    user: User = Depends(require_permissions("authorization.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AuthorizationService(db)
    role = await service.update_role(role_id, payload.name, payload.description)
    return RolePublic.model_validate(role)


@router.delete("/roles/{role_id}", response_model=MessageResponse)
async def delete_role(
    role_id: uuid.UUID,
    user: User = Depends(require_permissions("authorization.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AuthorizationService(db)
    await service.delete_role(role_id)
    return MessageResponse(message="Role deleted successfully.")


@router.put("/roles/{role_id}/permissions", response_model=RoleWithPermissions)
async def set_role_permissions(
    role_id: uuid.UUID,
    payload: AssignPermissionsRequest,
    user: User = Depends(require_permissions("authorization.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    service = AuthorizationService(db)
    role = await service.set_role_permissions(role_id, payload.permission_codes)
    return RoleWithPermissions(
        **RolePublic.model_validate(role).model_dump(),
        permissions=[PermissionPublic.model_validate(rp.permission) for rp in role.role_permissions],
    )


@router.post("/user-roles", response_model=MessageResponse)
async def assign_role_to_user(
    payload: AssignRoleRequest,
    user: User = Depends(require_permissions("authorization.roles.assign")),
    db: AsyncSession = Depends(get_db),
):
    service = AuthorizationService(db)
    await service.assign_role(payload.user_id, payload.role_id, assigned_by_user_id=user.id)
    return MessageResponse(message="Role assigned successfully.")


@router.delete("/user-roles", response_model=MessageResponse)
async def revoke_role_from_user(
    payload: AssignRoleRequest,
    user: User = Depends(require_permissions("authorization.roles.assign")),
    db: AsyncSession = Depends(get_db),
):
    service = AuthorizationService(db)
    await service.revoke_role(payload.user_id, payload.role_id)
    return MessageResponse(message="Role revoked successfully.")


@router.get("/users/{user_id}/roles", response_model=UserRolesResponse)
async def get_user_roles(
    user_id: uuid.UUID,
    user: User = Depends(require_permissions("authorization.roles.view", "users.view", require_all=False)),
    db: AsyncSession = Depends(get_db),
):
    service = AuthorizationService(db)
    result = await service.get_user_roles_and_permissions(user_id)
    return UserRolesResponse(
        user_id=user_id,
        roles=[RolePublic.model_validate(r) for r in result["roles"]],
        effective_permissions=result["effective_permissions"],
    )
