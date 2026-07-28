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

from fastapi import FastAPI, Request, status
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
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error",
                "Request validation failed.",
                exc.errors(),
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
