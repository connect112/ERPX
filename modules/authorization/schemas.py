"""
Authorization module — Pydantic schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PermissionPublic(BaseModel):
    id: uuid.UUID
    code: str
    module: str
    description: str | None

    model_config = {"from_attributes": True}


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9_]+$")
    description: str | None = None


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None


class RolePublic(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    is_system: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleWithPermissions(RolePublic):
    permissions: list[PermissionPublic] = []


class AssignPermissionsRequest(BaseModel):
    permission_codes: list[str] = Field(..., min_length=1)


class AssignRoleRequest(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID


class RevokeRoleRequest(BaseModel):
    user_id: uuid.UUID
    role_id: uuid.UUID


class UserRolesResponse(BaseModel):
    user_id: uuid.UUID
    roles: list[RolePublic]
    effective_permissions: list[str]


class MessageResponse(BaseModel):
    message: str
