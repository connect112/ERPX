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
    # Browsers upload and download files straight to storage through presigned URLs, but the storage
    # server is only reachable inside the server network (as `minio:9000`). When this is set (for
    # example "/_files"), presigned URLs are returned as "<this prefix>/<bucket>/<key>?<signature>"
    # instead, relative to the site the user is on; the web server must forward that prefix to the
    # storage server and send it `Host: <MINIO_ENDPOINT>`, which is what the signature was made for.
    # Empty = URLs are returned as they are (storage reachable from the browser, e.g. local development).
    STORAGE_PUBLIC_PREFIX: str = ""

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
    # 5173/3000 = apps/web, 5174 = apps/student-portal (see apps/student-portal/vite.config.ts).
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:5174"

    # ---- Live classes (self-hosted Jitsi Meet) ----
    # The dedicated Jitsi server (infrastructure/aws-single-host — a
    # separate EC2 instance from the main ERPX host, since JVB needs real
    # CPU for media relay). Empty JITSI_PUBLIC_URL (the default) means
    # live classes fall back to a trainer-supplied meeting_link instead of
    # an auto-provisioned room — local dev and every test run are
    # unaffected by this.
    JITSI_PUBLIC_URL: str = ""
    # Must exactly match JWT_APP_ID / JWT_APP_SECRET in the Jitsi server's
    # own .env (see modules/live_classes/jitsi.py) — Prosody's token auth
    # plugin verifies every join JWT against this same secret.
    JITSI_APP_ID: str = "erpx"
    JITSI_APP_SECRET: str = ""
    # How long a minted join JWT stays valid — generous over a typical
    # class's duration_minutes so a long session doesn't get cut off
    # mid-call; the token only grants access to one specific room anyway.
    JITSI_TOKEN_EXPIRE_MINUTES: int = 240

    # ---- Single sign-on (cross-subdomain) ----
    # Domain attribute for the `erpx_sso` cookie modules/authentication/routes.py
    # sets at /login and /refresh — e.g. ".pentrix.in" in production, so the
    # same cookie is visible to erp./lms./staff./trainer.pentrix.in and
    # /auth/sso/bootstrap on any of them can silently pick up a session
    # started on any other. Empty (the default) disables the cookie
    # entirely — local dev and every test run behave exactly as before.
    SSO_COOKIE_DOMAIN: str = ""
    # The cookie itself carries no Max-Age (a browser-session cookie — see
    # _set_sso_cookie), so it's gone once the browser is fully closed. This
    # is a second, server-side cap for the case a browser restores its
    # session across a restart anyway: a cookie whose underlying refresh
    # token is older than this is rejected by /auth/sso/bootstrap even
    # though the token itself hasn't hit its full REFRESH_TOKEN_EXPIRE_DAYS
    # expiry — silently signing someone into a *different* account than
    # whoever is sitting at the keyboard should have a much shorter window
    # than "stay logged in on this one portal for a week", which is what a
    # deliberately-kept session on a single portal is for. Found live: a
    # shared/reused test browser silently bootstrapped a stale account's
    # session on a fresh visit days after that account last explicitly
    # used it, with zero re-authentication.
    SSO_BRIDGE_MAX_AGE_HOURS: int = 24

    # ---- Rate Limiting ----
    RATE_LIMIT_DEFAULT: str = "100/minute"
    # Per-IP caps on login and on setting a password from an emailed link.
    # A hackathon/workshop room puts a couple of hundred students behind one
    # venue IP, so organisers raise these (env) for the event and put them
    # back afterwards. Per-account lockout after repeated failures is
    # separate and unaffected.
    AUTH_LOGIN_RATE_LIMIT: str = "10/minute"
    AUTH_RESET_PASSWORD_RATE_LIMIT: str = "5/minute"
    # Per-IP cap for the anonymous landing-page view beacon
    # (POST /marketing/landing-pages/{id}/views). Generous for a real
    # visitor (one beacon per page load) but bounds automated view-count
    # inflation / write floods on this unauthenticated endpoint.
    RATE_LIMIT_PUBLIC_VIEW: str = "30/minute"

    # ---- Frontend ----
    FRONTEND_URL: str = "http://localhost:5173"
    # apps/student-portal — where a provisioned student's "set your
    # password" email link and login_url point (see modules/provisioning).
    STUDENT_PORTAL_URL: str = "http://localhost:5174"
    # apps/employee-portal — where an invited employee's "set your
    # password" email link and login_url point (see modules/employees'
    # invite_employee).
    EMPLOYEE_PORTAL_URL: str = "http://localhost:5175"

    # ---- Internal service-to-service auth ----
    # Shared HMAC secret verifying inbound calls to /api/v1/internal/*
    # (currently just modules/provisioning) — mirrors the signed-body
    # pattern Pentrix-share's own razorpay/stripe webhook adapters already
    # use, rather than a bearer token or network-level (nginx) allowlist.
    # Empty by default: modules/provisioning/dependencies.py fails closed
    # (rejects every call) when this is unset, rather than silently
    # comparing against an empty secret.
    ERPX_INTERNAL_SERVICE_SECRET: str = ""

    # A separate secret (not ERPX_INTERNAL_SERVICE_SECRET) for the
    # self-hosted Jitsi recording server's finalize script to call
    # POST /live-classes/recording-webhook once a recording has been
    # uploaded — a distinct trust boundary from Pentrix-share's
    # provisioning calls, so compromising one secret doesn't also expose
    # the other channel. Same fail-closed-when-unset behavior.
    JIBRI_WEBHOOK_SECRET: str = ""

    # ---- Account Security ----
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    # ---- Distributed tracing (OpenTelemetry) ----
    # Disabled by default (a complete no-op) — see app/core/tracing.py. Enable
    # in staging/production to emit per-request span trees (HTTP + SQL + Redis
    # + outbound HTTP + Celery) over OTLP/HTTP to a Collector/Tempo/Jaeger.
    OTEL_TRACING_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318"
    OTEL_TRACES_SAMPLE_RATE: float = 0.1

    # ---- Response caching (Redis) ----
    # Caches read-only aggregate endpoints (dashboards/analytics/reports) in
    # the existing Redis. Set CACHE_ENABLED=false to disable globally; if
    # Redis is unreachable the cache degrades transparently (see
    # app/core/cache.py). TTLs are in seconds.
    CACHE_ENABLED: bool = True
    CACHE_TTL_DASHBOARD: int = 60
    CACHE_TTL_ANALYTICS: int = 120
    CACHE_TTL_REFERENCE: int = 300

    # ---- Error Tracking (Sentry) ----
    # Empty DSN (the default) disables Sentry entirely — no init, no network
    # calls, a pure no-op. This is the intended local-development behavior:
    # nothing to run or configure. Set a real DSN only in staging/production.
    SENTRY_DSN: str = ""
    # Falls back to ENVIRONMENT when left blank (see app/core/observability.py).
    SENTRY_ENVIRONMENT: str = ""
    SENTRY_RELEASE: str = ""
    # 0.0 = error/exception reporting only, no performance tracing (minimal,
    # zero sampling overhead). Raise (e.g. 0.1) to sample transaction traces.
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0

    # ---- AI Provider ----
    AI_PROVIDER: str = "anthropic"
    AI_API_KEY: str = ""
    AI_API_BASE_URL: str = "https://api.anthropic.com"
    AI_MODEL: str = "claude-sonnet-5"
    AI_MAX_TOKENS: int = 2048
    AI_REQUEST_TIMEOUT_SECONDS: int = 60

    # ---- Social Media: estimated AI cost (shown as an estimate; change if your provider's prices differ) ----
    SOCIAL_AI_INPUT_USD_PER_MTOK: float = 3.0
    SOCIAL_AI_OUTPUT_USD_PER_MTOK: float = 15.0
    SOCIAL_USD_TO_INR: float = 85.0

    # ---- Social Media: optional AI backgrounds (any "/v1/images/generations" compatible API) ----
    # All three must be set to turn it on. The picture is only ever a background: text and the logo are drawn by code.
    SOCIAL_IMAGE_API_KEY: str = ""
    SOCIAL_IMAGE_API_BASE_URL: str = ""
    SOCIAL_IMAGE_MODEL: str = ""
    SOCIAL_IMAGE_COST_INR: float = 4.0  # estimated cost of one background, for the budget

    # ---- Social Media: Instagram publishing ----
    # "Instagram API with Instagram Login" (graph.instagram.com). The version is configurable because Meta retires old ones.
    INSTAGRAM_GRAPH_BASE_URL: str = "https://graph.instagram.com"
    INSTAGRAM_GRAPH_VERSION: str = "v25.0"
    # A Fernet key (python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") used to
    # encrypt stored access tokens. Empty = derived from JWT_SECRET_KEY.
    SOCIAL_TOKEN_ENCRYPTION_KEY: str = ""

    # ---- Job feed (Placements) ----
    # Adzuna (https://developer.adzuna.com) and Jooble (https://jooble.org/api/about) are used only when their keys
    # are set; Remotive and Arbeitnow need no key.
    ADZUNA_APP_ID: str = ""
    ADZUNA_APP_KEY: str = ""
    JOOBLE_API_KEY: str = ""

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
