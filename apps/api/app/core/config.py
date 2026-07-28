"""
Centralized application configuration.

All environment-driven settings live here. Every other module imports
`settings` from this file instead of reading os.environ directly, which
keeps configuration auditable and makes testing (via dependency overrides)
straightforward.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET_KEY = "change_me_in_production_min_32_chars"
_MIN_JWT_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---- General ----
    PROJECT_NAME: str = "ERPX"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = Field(default=False)

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _derive_debug(cls, v, info):
        return v

    # ---- Database ----
    DATABASE_URL: str = (
        "postgresql+asyncpg://erpx:erpx_secret@postgres:5432/erpx"
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False
    PG_DUMP_PATH: str = "pg_dump"
    # The plain-SQL dumps modules/backups/service.py produces (no -Fc) are
    # replayed with psql, not pg_restore — see apps/api/scripts/restore_backup.py.
    PSQL_PATH: str = "psql"

    # ---- Redis / Celery ----
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # ---- JWT Auth ----
    JWT_SECRET_KEY: str = _DEFAULT_JWT_SECRET_KEY
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- Storage (MinIO / S3) ----
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "erpx_minio"
    MINIO_SECRET_KEY: str = "erpx_minio_secret"
    MINIO_BUCKET: str = "erpx-storage"
    MINIO_SECURE: bool = False

    # ---- Search ----
    ELASTICSEARCH_URL: str = "http://elasticsearch:9200"

    # ---- Email ----
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@erpx.example.com"
    SMTP_FROM_NAME: str = "ERPX"

    # ---- SMS (Fast2SMS — https://docs.fast2sms.com) ----
    SMS_PROVIDER_API_KEY: str = ""
    SMS_SENDER_ID: str = "ERPXTX"

    # ---- WhatsApp (Meta WhatsApp Cloud API) ----
    WHATSAPP_API_KEY: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""

    # ---- CORS ----
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # ---- Rate Limiting ----
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # ---- Frontend ----
    FRONTEND_URL: str = "http://localhost:5173"

    # ---- Account Security ----
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    # ---- AI Provider ----
    AI_PROVIDER: str = "anthropic"
    AI_API_KEY: str = ""
    AI_API_BASE_URL: str = "https://api.anthropic.com"
    AI_MODEL: str = "claude-sonnet-5"
    AI_MAX_TOKENS: int = 2048
    AI_REQUEST_TIMEOUT_SECONDS: int = 60

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @model_validator(mode="after")
    def _refuse_default_jwt_secret_in_production(self) -> "Settings":
        """
        Fail fast rather than silently serving traffic with a JWT signing
        secret that is publicly visible in this file's source code. Every
        access/refresh token would be forgeable — including for a
        superuser — by anyone who has ever seen this codebase. This is not
        a hardening nice-to-have: it's the difference between "production
        misconfiguration" and "complete authentication bypass," triggered
        by nothing more than forgetting to set one of ~30 env vars.
        """
        if not self.is_production:
            return self
        # Checked by substring, not exact match, because this codebase ships
        # more than one placeholder spelling: the Python field default above
        # ("change_me_in_production_min_32_chars") and .env's own scaffold
        # value ("change_me_to_a_random_64_char_secret_in_production") are
        # different strings — an exact-match check against only one of them
        # would silently let the other slip through. Both (like every other
        # placeholder in .env — SMTP_PASSWORD, SMS_PROVIDER_API_KEY,
        # WHATSAPP_API_KEY, AI_API_KEY) follow the same "change_me..."
        # convention, so that's the actual signal to check for.
        if "change_me" in self.JWT_SECRET_KEY.lower():
            raise ValueError(
                "JWT_SECRET_KEY is still a placeholder value while "
                "ENVIRONMENT=production. Set a real random secret "
                f"(at least {_MIN_JWT_SECRET_KEY_LENGTH} characters) before "
                "starting the application."
            )
        if len(self.JWT_SECRET_KEY) < _MIN_JWT_SECRET_KEY_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {_MIN_JWT_SECRET_KEY_LENGTH} "
                f"characters in production (got {len(self.JWT_SECRET_KEY)})."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. FastAPI dependencies should use this."""
    return Settings()


settings = get_settings()
