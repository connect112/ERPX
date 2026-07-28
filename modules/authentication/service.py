"""
Authentication module — service layer.

Orchestrates the repository, password hashing, JWT issuance, 2FA, and
email dispatch. Routes call this; this never touches SQLAlchemy directly.
"""

import base64
import io
import uuid
from datetime import datetime, timezone

import pyotp
import qrcode
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.core.security import (
    TokenPayloadError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from modules.authentication.models import User, UserStatus
from modules.authentication.repository import AuthRepository
from modules.authentication.schemas import RefreshTokenResponse, TokenResponse, UserPublic
from modules.authentication.tasks import (
    send_password_reset_email_task,
    send_verification_email_task,
)

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AuthRepository(db)

    # ---- Registration & email verification ----

    async def register(
        self, email: str, password: str, full_name: str, phone_number: str | None
    ) -> User:
        existing = await self.repo.get_user_by_email(email)
        if existing:
            raise ConflictError("An account with this email already exists.")

        user = await self.repo.create_user(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            phone_number=phone_number,
        )

        verification = await self.repo.create_email_verification_token(user.id)
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification.token}"
        send_verification_email_task.delay(user.email, user.full_name, verification_url)

        logger.info("user_registered", user_id=str(user.id), email=user.email)
        return user

    async def verify_email(self, token: str) -> User:
        token_row = await self.repo.get_email_verification_token(token)
        if not token_row or not token_row.is_valid:
            raise ValidationError("This verification link is invalid or has expired.")

        user = await self.repo.get_user_by_id(token_row.user_id)
        if not user:
            raise NotFoundError("User")

        await self.repo.mark_email_verified(user)
        await self.repo.mark_verification_token_used(token_row)
        logger.info("email_verified", user_id=str(user.id))
        return user

    async def resend_verification(self, email: str) -> None:
        user = await self.repo.get_user_by_email(email)
        if not user or user.is_email_verified:
            # Do not reveal whether the account exists or is already verified.
            return

        verification = await self.repo.create_email_verification_token(user.id)
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification.token}"
        send_verification_email_task.delay(user.email, user.full_name, verification_url)

    # ---- Login ----

    async def authenticate(
        self,
        email: str,
        password: str,
        otp_code: str | None,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenResponse | dict:
        user = await self.repo.get_user_by_email(email)

        # Constant-shape failure: don't reveal whether the email exists.
        if not user:
            raise AuthenticationError("Invalid email or password.")

        if user.is_locked:
            raise AuthenticationError(
                "This account is temporarily locked due to repeated failed login attempts. "
                "Please try again later."
            )

        if user.status == UserStatus.SUSPENDED:
            raise AuthenticationError("This account has been suspended. Contact support.")
        if user.status == UserStatus.DEACTIVATED:
            raise AuthenticationError("This account has been deactivated.")

        if not verify_password(password, user.hashed_password):
            await self.repo.register_failed_login(
                user, settings.MAX_LOGIN_ATTEMPTS, settings.ACCOUNT_LOCKOUT_MINUTES
            )
            logger.warning("login_failed_bad_password", user_id=str(user.id))
            raise AuthenticationError("Invalid email or password.")

        if not user.is_email_verified:
            raise AuthenticationError("Please verify your email address before logging in.")

        if user.two_factor_enabled:
            if not otp_code:
                return {"two_factor_required": True}
            totp = pyotp.TOTP(user.two_factor_secret)
            if not totp.verify(otp_code, valid_window=1):
                await self.repo.register_failed_login(
                    user, settings.MAX_LOGIN_ATTEMPTS, settings.ACCOUNT_LOCKOUT_MINUTES
                )
                raise AuthenticationError("Invalid two-factor authentication code.")

        await self.repo.reset_failed_logins(user)
        logger.info("login_success", user_id=str(user.id))

        return await self._issue_tokens(user, user_agent, ip_address)

    async def _issue_tokens(
        self, user: User, user_agent: str | None, ip_address: str | None
    ) -> TokenResponse:
        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))
        payload = decode_token(refresh_token, TokenType.REFRESH)

        await self.repo.store_refresh_token(
            user_id=user.id,
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserPublic.model_validate(user),
        )

    # ---- Token refresh & logout ----

    async def refresh(
        self, refresh_token: str, user_agent: str | None, ip_address: str | None
    ) -> RefreshTokenResponse:
        try:
            payload = decode_token(refresh_token, TokenType.REFRESH)
        except TokenPayloadError as exc:
            raise AuthenticationError("Invalid or expired refresh token.") from exc

        token_row = await self.repo.get_refresh_token(payload["jti"])
        if not token_row or not token_row.is_active:
            # Reuse of a revoked/expired token is a strong signal of theft:
            # revoke every session for this user as a precaution.
            if token_row:
                await self.repo.revoke_all_refresh_tokens_for_user(token_row.user_id)
            raise AuthenticationError("This session is no longer valid. Please log in again.")

        user = await self.repo.get_user_by_id(uuid.UUID(payload["sub"]))
        if not user or user.status != UserStatus.ACTIVE:
            raise AuthenticationError("This account is no longer active.")

        # Rotate: revoke the old refresh token, issue a brand new pair.
        await self.repo.revoke_refresh_token(payload["jti"])
        tokens = await self._issue_tokens(user, user_agent, ip_address)
        return _to_refresh_response(tokens)

    async def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token, TokenType.REFRESH)
        except TokenPayloadError:
            return
        await self.repo.revoke_refresh_token(payload["jti"])

    # ---- Password management ----

    async def forgot_password(self, email: str) -> None:
        user = await self.repo.get_user_by_email(email)
        if not user:
            # Do not reveal whether the account exists.
            return

        reset = await self.repo.create_password_reset_token(user.id)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset.token}"
        send_password_reset_email_task.delay(user.email, user.full_name, reset_url)

    async def reset_password(self, token: str, new_password: str) -> None:
        token_row = await self.repo.get_password_reset_token(token)
        if not token_row or not token_row.is_valid:
            raise ValidationError("This password reset link is invalid or has expired.")

        user = await self.repo.get_user_by_id(token_row.user_id)
        if not user:
            raise NotFoundError("User")

        await self.repo.set_password(user, hash_password(new_password))
        await self.repo.mark_reset_token_used(token_row)
        await self.repo.revoke_all_refresh_tokens_for_user(user.id)
        logger.info("password_reset", user_id=str(user.id))

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect.")
        await self.repo.set_password(user, hash_password(new_password))
        await self.repo.revoke_all_refresh_tokens_for_user(user.id)
        logger.info("password_changed", user_id=str(user.id))

    # ---- Two-factor authentication ----

    async def setup_two_factor(self, user: User) -> dict:
        secret = pyotp.random_base32()
        await self.repo.set_two_factor_secret(user, secret)

        totp = pyotp.TOTP(secret)
        otpauth_url = totp.provisioning_uri(name=user.email, issuer_name="ERPX")

        qr = qrcode.make(otpauth_url)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return {"secret": secret, "otpauth_url": otpauth_url, "qr_code_base64": qr_code_base64}

    async def confirm_two_factor(self, user: User, otp_code: str) -> None:
        if not user.two_factor_secret:
            raise ValidationError("Two-factor setup has not been initiated for this account.")
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(otp_code, valid_window=1):
            raise ValidationError("Invalid verification code.")
        await self.repo.set_two_factor_enabled(user, True)
        logger.info("two_factor_enabled", user_id=str(user.id))

    async def disable_two_factor(self, user: User, otp_code: str) -> None:
        if not user.two_factor_enabled or not user.two_factor_secret:
            raise ValidationError("Two-factor authentication is not enabled on this account.")
        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(otp_code, valid_window=1):
            raise ValidationError("Invalid verification code.")
        await self.repo.set_two_factor_enabled(user, False)
        await self.repo.set_two_factor_secret(user, None)
        logger.info("two_factor_disabled", user_id=str(user.id))


def _to_refresh_response(tokens: TokenResponse) -> RefreshTokenResponse:
    """Refresh responses omit the `user` field; reuses the same token pair shape."""
    return RefreshTokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )
