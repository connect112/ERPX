"""
Application-wide exception hierarchy.

Every module raises these instead of raw HTTPException so that error
shape, error codes, and logging are consistent everywhere. The handlers
in app/core/exception_handlers.py catch these and turn them into the
standard ERPX error envelope.
"""

from typing import Any


class ERPXException(Exception):
    """Base class for all application-level exceptions."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str = "An unexpected error occurred.", details: Any = None):
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(ERPXException):
    status_code = 404
    error_code = "not_found"

    def __init__(self, resource: str = "Resource", identifier: Any = None):
        message = f"{resource} not found" + (f": {identifier}" if identifier else "")
        super().__init__(message)


class ValidationError(ERPXException):
    status_code = 422
    error_code = "validation_error"


class AuthenticationError(ERPXException):
    status_code = 401
    error_code = "authentication_error"

    def __init__(self, message: str = "Authentication credentials were not valid."):
        super().__init__(message)


class AuthorizationError(ERPXException):
    status_code = 403
    error_code = "authorization_error"

    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(message)


class ConflictError(ERPXException):
    status_code = 409
    error_code = "conflict"


class RateLimitError(ERPXException):
    status_code = 429
    error_code = "rate_limit_exceeded"

    def __init__(self, message: str = "Too many requests. Please try again later."):
        super().__init__(message)


class ServiceUnavailableError(ERPXException):
    status_code = 503
    error_code = "service_unavailable"
