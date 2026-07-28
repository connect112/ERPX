"""
Authentication module — Pydantic schemas (request/response contracts).
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from modules.authentication.models import UserStatus

PASSWORD_MIN_LENGTH = 8


def _validate_password_strength(password: str) -> str:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain at least one special character.")
    return password


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)
    phone_number: str | None = Field(default=None, max_length=32)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str
    otp_code: str | None = Field(default=None, min_length=6, max_length=6)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class TwoFactorVerifyRequest(BaseModel):
    otp_code: str = Field(..., min_length=6, max_length=6)


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_url: str
    qr_code_base64: str


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone_number: str | None
    status: UserStatus
    is_email_verified: bool
    two_factor_enabled: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class MessageResponse(BaseModel):
    message: str


class TwoFactorRequiredResponse(BaseModel):
    two_factor_required: bool = True
    message: str = "Two-factor authentication code required."
