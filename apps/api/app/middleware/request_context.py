"""
Middleware that attaches a request ID to every request/response pair and
emits a structured access log line. The request ID is echoed back in the
`X-Request-ID` response header and included in every error envelope,
which makes cross-referencing client-reported issues with server logs
trivial.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.audit_context import set_audit_request_metadata
from app.core.logging_config import get_logger

logger = get_logger("access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        set_audit_request_metadata(
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            request_id=request_id,
        )
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
        return response
