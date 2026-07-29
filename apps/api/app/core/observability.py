"""
Sentry error-tracking integration (Production Hardening Audit finding #10).

Centralizes Sentry SDK initialization for both entrypoints — the FastAPI
API process (`app/main.py`) and the Celery worker/beat process
(`app/core/celery_app.py`) — mirroring how `configure_logging()` is shared
across the same two entrypoints.

Behavior is entirely environment-driven and safe by default:

- `SENTRY_DSN` is empty by default, which DISABLES Sentry (no init, no
  network calls, a pure no-op). This is the intended local-development
  behavior — nothing to run, nothing to configure. Sentry activates only
  when a real DSN is provided (staging/production).
- `send_default_pii=False` is forced, so Sentry never attaches request
  bodies, cookies, the `Authorization` header, or the client IP. A
  `before_send` hook additionally redacts sensitive headers as defense in
  depth, layered on top of Sentry's built-in `EventScrubber` (which redacts
  values for keys like `password`/`secret`/`token`/`api_key`).
- No performance tracing by default (`SENTRY_TRACES_SAMPLE_RATE=0.0`) — this
  is minimal error aggregation only.

Sentry's default auto-enabled integrations cover all three required capture
targets: FastAPI/Starlette request exceptions, Celery task failures, and
process-level unhandled exceptions. The catch-all `Exception` handler in
`app/core/exception_handlers.py` also calls `sentry_sdk.capture_exception()`
explicitly, because a *handled* 500 (which that handler produces by returning
a JSON envelope) would otherwise not propagate to Starlette's server-error
layer for the framework integration to observe. Sentry's default
`DedupeIntegration` prevents any double reporting if both paths ever fire.
"""

from __future__ import annotations

from typing import Any

import sentry_sdk

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Headers that may carry credentials or session material. `send_default_pii`
# is already False (so the integrations don't attach these), but we filter
# explicitly in case a future integration or manual scope adds them.
_SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key", "x-csrf-token"}


def _scrub_sensitive_data(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any]:
    """
    `before_send` hook: strip request data that could carry credentials or
    session material, on top of `send_default_pii=False` and Sentry's default
    `EventScrubber`.
    """
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            for key in list(headers.keys()):
                if key.lower() in _SENSITIVE_HEADERS:
                    headers[key] = "[Filtered]"
    return event


def init_sentry(service_name: str) -> bool:
    """
    Initialize Sentry for the given service (``"erpx-api"`` / ``"erpx-celery"``).

    Returns True if Sentry was initialized (a DSN was configured), False if it
    was left disabled. Call once per process at startup.
    """
    if not settings.SENTRY_DSN:
        logger.info(
            "sentry_disabled",
            service=service_name,
            reason="no SENTRY_DSN configured",
        )
        return False

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
        release=settings.SENTRY_RELEASE or None,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        # Never send PII: no request bodies, cookies, auth headers, or client IP.
        send_default_pii=False,
        before_send=_scrub_sensitive_data,
    )
    sentry_sdk.set_tag("service", service_name)
    logger.info(
        "sentry_initialized",
        service=service_name,
        environment=settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )
    return True
