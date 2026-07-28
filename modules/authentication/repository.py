"""
Authentication module — repository layer.

Implements the Repository pattern: `AuthService` never touches SQLAlchemy
directly, it calls methods here. Keeps query logic centralized and
independently testable/mockable.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.authentication.models import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserStatus,
)


class AuthRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- Users ----

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        hashed_password: str,
        full_name: str,
        phone_number: str | None = None,
    ) -> User:
        user = User(
            email=email.lower(),
            hashed_password=hashed_password,
            full_name=full_name,
            phone_number=phone_number,
            status=UserStatus.PENDING_VERIFICATION,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def register_failed_login(self, user: User, max_attempts: int, lockout_minutes: int) -> None:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= max_attempts:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
        await self.db.flush()

    async def reset_failed_logins(self, user: User) -> None:
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def set_password(self, user: User, hashed_password: str) -> None:
        user.hashed_password = hashed_password
        await self.db.flush()

    async def mark_email_verified(self, user: User) -> None:
        user.is_email_verified = True
        user.status = UserStatus.ACTIVE
        await self.db.flush()

    async def set_two_factor_secret(self, user: User, secret: str | None) -> None:
        user.two_factor_secret = secret
        await self.db.flush()

    async def set_two_factor_enabled(self, user: User, enabled: bool) -> None:
        user.two_factor_enabled = enabled
        await self.db.flush()

    # ---- Refresh tokens ----

    async def store_refresh_token(
        self,
        user_id: uuid.UUID,
        jti: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_jti=jti,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_refresh_token(self, jti: str) -> RefreshToken | None:
        result = await self.db.execute(select(RefreshToken).where(RefreshToken.token_jti == jti))
        return result.scalar_one_or_none()

    async def revoke_refresh_token(self, jti: str) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_jti == jti)
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self.db.flush()

    async def revoke_all_refresh_tokens_for_user(self, user_id: uuid.UUID) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self.db.flush()

    # ---- Email verification tokens ----

    async def create_email_verification_token(self, user_id: uuid.UUID, ttl_hours: int = 24) -> EmailVerificationToken:
        token = EmailVerificationToken(
            user_id=user_id,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        )
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_email_verification_token(self, token: str) -> EmailVerificationToken | None:
        result = await self.db.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.token == token)
        )
        return result.scalar_one_or_none()

    async def mark_verification_token_used(self, token_row: EmailVerificationToken) -> None:
        token_row.used_at = datetime.now(timezone.utc)
        await self.db.flush()

    # ---- Password reset tokens ----

    async def create_password_reset_token(self, user_id: uuid.UUID, ttl_hours: int = 1) -> PasswordResetToken:
        token = PasswordResetToken(
            user_id=user_id,
            token=secrets.token_urlsafe(32),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        )
        self.db.add(token)
        await self.db.flush()
        return token

    async def get_password_reset_token(self, token: str) -> PasswordResetToken | None:
        result = await self.db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == token)
        )
        return result.scalar_one_or_none()

    async def mark_reset_token_used(self, token_row: PasswordResetToken) -> None:
        token_row.used_at = datetime.now(timezone.utc)
        await self.db.flush()
