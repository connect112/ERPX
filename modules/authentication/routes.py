"""
Authentication module — routes.

Registered under /api/v1/auth in app/api/v1/router.py.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import limiter
from app.db.session import get_db
from modules.authentication.dependencies import get_current_active_user
from modules.authentication.models import User
from modules.authentication.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    TwoFactorSetupResponse,
    TwoFactorVerifyRequest,
    UserLoginRequest,
    UserPublic,
    UserRegisterRequest,
    VerifyEmailRequest,
)
from modules.authentication.service import AuthService

router = APIRouter()


def _client_context(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(payload: UserRegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
    )
    return UserPublic.model_validate(user)


@router.post("/login")
@limiter.limit("10/minute")
async def login(payload: UserLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user_agent, ip_address = _client_context(request)
    result = await service.authenticate(
        email=payload.email,
        password=payload.password,
        otp_code=payload.otp_code,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return result


@router.post("/refresh", response_model=RefreshTokenResponse)
@limiter.limit("20/minute")
async def refresh(payload: RefreshTokenRequest, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user_agent, ip_address = _client_context(request)
    return await service.refresh(payload.refresh_token, user_agent, ip_address)


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.logout(payload.refresh_token)
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserPublic)
async def get_me(user: User = Depends(get_current_active_user)):
    return UserPublic.model_validate(user)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.verify_email(payload.token)
    return MessageResponse(message="Email verified successfully. You can now log in.")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit("5/minute")
async def resend_verification(
    payload: ResendVerificationRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    await service.resend_verification(payload.email)
    return MessageResponse(
        message="If an account with that email exists, a verification link has been sent."
    )


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("5/minute")
async def forgot_password(payload: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.forgot_password(payload.email)
    return MessageResponse(
        message="If an account with that email exists, a password reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("5/minute")
async def reset_password(payload: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.reset_password(payload.token, payload.new_password)
    return MessageResponse(message="Password reset successfully. You can now log in.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.change_password(user, payload.current_password, payload.new_password)
    return MessageResponse(message="Password changed successfully.")


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor(
    user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    result = await service.setup_two_factor(user)
    return TwoFactorSetupResponse(**result)


@router.post("/2fa/confirm", response_model=MessageResponse)
async def confirm_two_factor(
    payload: TwoFactorVerifyRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.confirm_two_factor(user, payload.otp_code)
    return MessageResponse(message="Two-factor authentication enabled.")


@router.post("/2fa/disable", response_model=MessageResponse)
async def disable_two_factor(
    payload: TwoFactorVerifyRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.disable_two_factor(user, payload.otp_code)
    return MessageResponse(message="Two-factor authentication disabled.")
