"""
Authorization module — repository layer.
"""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.authorization.models import Permission, Role, RolePermission, UserRole


class AuthorizationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_roles(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Role))
        return result.scalar_one()

    # ---- Roles ----

    async def create_role(self, name: str, slug: str, description: str | None) -> Role:
        role = Role(name=name, slug=slug, description=description, is_system=False)
        self.db.add(role)
        await self.db.flush()
        await self.db.refresh(role)
        return role

    async def get_role_by_id(self, role_id: uuid.UUID) -> Role | None:
        result = await self.db.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def get_role_by_slug(self, slug: str) -> Role | None:
        result = await self.db.execute(select(Role).where(Role.slug == slug))
        return result.scalar_one_or_none()

    async def list_roles(self) -> list[Role]:
        result = await self.db.execute(select(Role).order_by(Role.name))
        return list(result.scalars().all())

    async def update_role(self, role: Role, name: str | None, description: str | None) -> Role:
        if name is not None:
            role.name = name
        if description is not None:
            role.description = description
        await self.db.flush()
        return role

    async def delete_role(self, role: Role) -> None:
        await self.db.delete(role)
        await self.db.flush()

    async def get_role_with_permissions(self, role_id: uuid.UUID) -> Role | None:
        result = await self.db.execute(
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
        )
        return result.scalar_one_or_none()

    # ---- Permissions ----

    async def list_permissions(self) -> list[Permission]:
        result = await self.db.execute(select(Permission).order_by(Permission.module, Permission.code))
        return list(result.scalars().all())

    async def get_permissions_by_codes(self, codes: list[str]) -> list[Permission]:
        result = await self.db.execute(select(Permission).where(Permission.code.in_(codes)))
        return list(result.scalars().all())

    async def get_or_create_permission(
        self, code: str, module: str, description: str | None = None
    ) -> Permission:
        result = await self.db.execute(select(Permission).where(Permission.code == code))
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        permission = Permission(code=code, module=module, description=description)
        self.db.add(permission)
        await self.db.flush()
        return permission

    # ---- Role <-> Permission ----

    async def set_role_permissions(self, role: Role, permissions: list[Permission]) -> None:
        await self.db.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        await self.db.flush()
        for permission in permissions:
            self.db.add(RolePermission(role_id=role.id, permission_id=permission.id))
        await self.db.flush()

    # ---- User <-> Role ----

    async def assign_role(
        self, user_id: uuid.UUID, role_id: uuid.UUID, assigned_by_user_id: uuid.UUID | None
    ) -> UserRole:
        existing = await self.db.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        )
        row = existing.scalar_one_or_none()
        if row:
            return row

        user_role = UserRole(
            user_id=user_id, role_id=role_id, assigned_by_user_id=assigned_by_user_id
        )
        self.db.add(user_role)
        await self.db.flush()
        return user_role

    async def revoke_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        await self.db.execute(
            delete(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
        )
        await self.db.flush()

    async def get_roles_for_user(self, user_id: uuid.UUID) -> list[Role]:
        result = await self.db.execute(
            select(Role).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_permission_codes_for_user(self, user_id: uuid.UUID) -> set[str]:
        result = await self.db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        return set(result.scalars().all())
