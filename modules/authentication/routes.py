"""
Authentication module — routes.

Registered under /api/v1/auth in app/api/v1/router.py.
"""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError
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

# Cookie mirroring the refresh token across every ERPX subdomain — see
# settings.SSO_COOKIE_DOMAIN and POST /sso/bootstrap below.
SSO_COOKIE_NAME = "erpx_sso"


def _client_context(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


def _set_sso_cookie(response: Response, refresh_token: str) -> None:
    """
    Mirrors a refresh token into a cookie shared across every ERPX
    subdomain (Domain=.pentrix.in in production), so a session started on
    one subdomain can be picked up silently on another via
    /auth/sso/bootstrap — no second login. A no-op whenever
    SSO_COOKIE_DOMAIN is unset (local dev and every test run), so nothing
    about existing behavior changes there.
    """
    if not settings.SSO_COOKIE_DOMAIN:
        return
    response.set_cookie(
        key=SSO_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        domain=settings.SSO_COOKIE_DOMAIN,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def _clear_sso_cookie(response: Response) -> None:
    if not settings.SSO_COOKIE_DOMAIN:
        return
    response.delete_cookie(key=SSO_COOKIE_NAME, domain=settings.SSO_COOKIE_DOMAIN, path="/")


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
async def login(
    payload: UserLoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    user_agent, ip_address = _client_context(request)
    result = await service.authenticate(
        email=payload.email,
        password=payload.password,
        otp_code=payload.otp_code,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    if isinstance(result, TokenResponse):
        _set_sso_cookie(response, result.refresh_token)
    return result


@router.post("/refresh", response_model=RefreshTokenResponse)
@limiter.limit("20/minute")
async def refresh(
    payload: RefreshTokenRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    user_agent, ip_address = _client_context(request)
    tokens = await service.refresh(payload.refresh_token, user_agent, ip_address)
    _set_sso_cookie(response, tokens.refresh_token)
    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: LogoutRequest, response: Response, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.logout(payload.refresh_token)
    _clear_sso_cookie(response)
    return MessageResponse(message="Logged out successfully.")


@router.post("/sso/bootstrap", response_model=TokenResponse)
@limiter.limit("30/minute")
async def sso_bootstrap(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Silent cross-subdomain login. Exchanges the shared `erpx_sso` cookie
    (set at /login and /refresh above — see settings.SSO_COOKIE_DOMAIN) for
    a fresh access/refresh token pair, so someone who already authenticated
    on one ERPX subdomain doesn't have to log in again on another.

    401 with no cookie, or an invalid/expired one — every portal's
    use-sso-bootstrap hook treats that as "no session" and falls back to
    its normal login page rather than surfacing this as an error.
    """
    session_token = request.cookies.get(SSO_COOKIE_NAME)
    if not session_token:
        raise AuthenticationError("No active cross-portal session.")

    service = AuthService(db)
    user_agent, ip_address = _client_context(request)
    tokens = await service.sso_bootstrap(session_token, user_agent, ip_address)
    _set_sso_cookie(response, tokens.refresh_token)
    return tokens


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
