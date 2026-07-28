"""
Authentication module — ORM models.

`User` is the credential/identity record every other module references
by foreign key (organizations, employees, students, etc. all link back
to users.id). Role/permission assignment lives in the Authorization
module (built next); this module owns only identity, credentials, and
session/verification lifecycle.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_model import SoftDeleteMixin, TimestampedBase


class UserStatus(str, enum.Enum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class User(TimestampedBase, SoftDeleteMixin):
    __tablename__ = "users"

    # Read by modules.audit.hooks — these columns are never written into an
    # audit row's before/after snapshot, even though the User entity itself
    # (status, is_superuser, etc.) is audited like anything else.
    __audit_exclude_fields__ = {"hashed_password", "two_factor_secret"}

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[UserStatus] = mapped_column(
        SAEnum(
            UserStatus,
            name="user_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=UserStatus.PENDING_VERIFICATION,
        server_default=UserStatus.PENDING_VERIFICATION.value,
        nullable=False,
    )
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    two_factor_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)

    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_locked(self) -> bool:
        return self.locked_until is not None and self.locked_until > _utcnow()


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class RefreshToken(TimestampedBase):
    """
    Server-side record of every issued refresh token, keyed by JWT `jti`.

    Storing these (rather than trusting the JWT alone) is what makes
    logout, forced session revocation, and rotation-reuse detection
    possible.
    """

    __tablename__ = "refresh_tokens"

    # Read by modules.audit.hooks — session plumbing created/revoked on
    # every login/logout would flood the audit trail with no compliance
    # value; the meaningful events (login, logout) are logged explicitly
    # by modules.authentication.service instead.
    __audit_skip__ = True

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > _utcnow()


class EmailVerificationToken(TimestampedBase):
    __tablename__ = "email_verification_tokens"

    # Read by modules.audit.hooks — holds a raw, single-use bearer token;
    # must never be written into an audit row.
    __audit_skip__ = True

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > _utcnow()


class PasswordResetToken(TimestampedBase):
    __tablename__ = "password_reset_tokens"

    # Read by modules.audit.hooks — holds a raw, single-use bearer token;
    # must never be written into an audit row.
    __audit_skip__ = True

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > _utcnow()
