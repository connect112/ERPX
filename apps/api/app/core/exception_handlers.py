"""
Global FastAPI exception handlers.

Guarantees a single, consistent JSON error envelope for every failure
mode across every module:

{
  "success": false,
  "error": {
    "code": "not_found",
    "message": "...",
    "details": null,
    "request_id": "..."
  }
}
"""

import uuid

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import ERPXException
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _envelope(code: str, message: str, details=None, request_id: str | None = None) -> dict:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id or str(uuid.uuid4()),
        },
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ERPXException)
    async def erpx_exception_handler(request: Request, exc: ERPXException):
        request_id = getattr(request.state, "request_id", None)
        logger.warning(
            "handled_exception",
            code=exc.error_code,
            message=exc.message,
            path=request.url.path,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.error_code, exc.message, exc.details, request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        # ``exc.errors()`` can carry non-JSON-serialisable values in each entry's
        # ``input``/``ctx`` (e.g. the raw request body as ``bytes`` when a client
        # posts a wrong content-type to a JSON endpoint). Passing them straight to
        # ``json.dumps`` raised ``TypeError: Object of type bytes is not JSON
        # serializable``, which the fallback handler turned into a 500 — masking
        # what should be a clean 422. ``jsonable_encoder`` coerces those values
        # (bytes -> str, etc.), matching FastAPI's own default validation handler.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error",
                "Request validation failed.",
                jsonable_encoder(exc.errors()),
                request_id,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(exc.detail), None, request_id),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        # Report to Sentry explicitly: this handler returns a JSON envelope,
        # so Starlette treats the 500 as "handled" and it never reaches the
        # server-error layer the framework integration hooks — without this
        # call these unhandled application errors would go uncaptured. No-op
        # when SENTRY_DSN is unset. Deduplicated by Sentry if also seen by an
        # integration. Tagged with the request_id for log cross-referencing.
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("request_id", request_id)
            sentry_sdk.capture_exception(exc)
        logger.exception(
            "unhandled_exception",
            path=request.url.path,
            request_id=request_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                "internal_error",
                "An unexpected error occurred. Our team has been notified.",
                None,
                request_id,
            ),
        )
