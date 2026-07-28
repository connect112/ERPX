"""
Authorization module — ORM models.

Implements classic RBAC: Users are assigned Roles (`UserRole`), Roles are
granted Permissions (`RolePermission`). A user's effective permission set
is the union of every permission attached to every role they hold.
`User.is_superuser` (Authentication module) bypasses all permission
checks entirely — see `modules/authorization/dependencies.py`.

This module imports `User` from Authentication directly (one-directional
dependency: Authorization depends on Authentication, never the reverse)
rather than adding a back-reference on `User`, which keeps the two
modules decoupled — querying a user's roles always goes through
`AuthorizationRepository`, never through a `user.roles` attribute.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_model import TimestampedBase
from modules.authentication.models import User  # noqa: F401  (relationship target)


class Role(TimestampedBase):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # System roles (Super Admin, etc.) ship with the platform and cannot be
    # deleted or renamed — only their permission set can be adjusted.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class Permission(TimestampedBase):
    __tablename__ = "permissions"

    # Dot-namespaced code, e.g. "crm.leads.create", "authorization.roles.manage".
    code: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="permission", cascade="all, delete-orphan"
    )


class RolePermission(TimestampedBase):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role: Mapped["Role"] = relationship(back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship(back_populates="role_permissions")


class UserRole(TimestampedBase):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    role: Mapped["Role"] = relationship(back_populates="user_roles")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
