"""
Security response headers applied to every response.

These are defense-in-depth for a JSON API primarily consumed by the
ERPX frontend (not a server-rendered HTML app), but cost nothing and
close off classes of attack (MIME sniffing, clickjacking of any HTML
error pages, leaking full referrer URLs to third parties) that a
"production-ready" API should not ship without.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        if settings.is_production:
            # Only set once TLS is guaranteed to be in front of the API —
            # a dev/staging box served over plain HTTP would lock browsers
            # out via HSTS if this were sent unconditionally.
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

        return response
