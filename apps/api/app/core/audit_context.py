"""
Request-scoped audit context.

`modules.audit.hooks` (the SQLAlchemy event listeners that actually write
audit rows) needs to know *who* is making a change and *where the request
came from*, but that information only exists at the HTTP layer — the
ORM flush that triggers an audit entry has no idea whether it's running
inside a request, a Celery task, or a seed script.

`RequestContextMiddleware` populates the IP/user-agent/request-id values
for every request; `get_current_user` (Authentication) and
`get_current_user_organization_id` (Users) populate the user/organization
once auth resolves. Everything defaults to None, so code paths with no
HTTP request (Celery tasks, `scripts/seed.py`) simply produce audit rows
attributed to no user — never an error.

ContextVars are per-asyncio-Task, and every ASGI request runs in its own
Task, so concurrent requests never see each other's values without any
explicit locking or cleanup required.

These same setters also bind into `structlog.contextvars` (a distinct
ContextVar-backed store structlog merges into every log line via
`merge_contextvars` in `app/core/logging_config.py`'s processor chain) so
`request_id`/`user_id`/`organization_id` appear in *every* application log
line emitted during a request, not only in `AuditLog` rows — one call site
per value, reused for both destinations rather than a second parallel
resolution mechanism. Log correlation is therefore only ever as complete
as audit correlation already is: a request that never resolves an
organization (e.g. no `get_current_user_organization_id` dependency in its
chain) legitimately has no `organization_id` in either place, exactly
mirroring `AuditLog.organization_id`'s existing nullability.
"""

import uuid
from contextvars import ContextVar

import structlog

_user_id: ContextVar[uuid.UUID | None] = ContextVar("audit_user_id", default=None)
_organization_id: ContextVar[uuid.UUID | None] = ContextVar("audit_organization_id", default=None)
_ip_address: ContextVar[str | None] = ContextVar("audit_ip_address", default=None)
_user_agent: ContextVar[str | None] = ContextVar("audit_user_agent", default=None)
_request_id: ContextVar[str | None] = ContextVar("audit_request_id", default=None)


def set_audit_request_metadata(ip_address: str | None, user_agent: str | None, request_id: str | None) -> None:
    _ip_address.set(ip_address)
    _user_agent.set(user_agent)
    _request_id.set(request_id)
    structlog.contextvars.bind_contextvars(request_id=request_id)


def set_audit_user(user_id: uuid.UUID | None) -> None:
    _user_id.set(user_id)
    structlog.contextvars.bind_contextvars(user_id=str(user_id) if user_id else None)


def set_audit_organization(organization_id: uuid.UUID | None) -> None:
    _organization_id.set(organization_id)
    structlog.contextvars.bind_contextvars(organization_id=str(organization_id) if organization_id else None)


def get_audit_context() -> dict:
    return {
        "user_id": _user_id.get(),
        "organization_id": _organization_id.get(),
        "ip_address": _ip_address.get(),
        "user_agent": _user_agent.get(),
        "request_id": _request_id.get(),
    }
