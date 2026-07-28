"""
Structured logging configuration using structlog.

Every module should obtain its logger via `get_logger(__name__)` rather
than the stdlib `logging.getLogger` directly, so that all log output is
uniformly structured JSON in production (human-readable in development)
with a consistent schema:

    timestamp, level, message, service, environment, request_id,
    organization_id, user_id, module, logger, hostname,
    pod_container_metadata, exception_details

`request_id`/`organization_id`/`user_id` are request-scoped — bound via
`app/core/audit_context.py`'s setters, reusing the same call sites that
already populate `AuditLog` rows, not a second resolution mechanism.
`service`/`environment`/`hostname`/`pod_container_metadata` are process-wide
constants, injected by `_static_fields_processor` below (deliberately not
contextvars-based, since they don't vary per request/task).

`configure_logging()` must be called once per process before any log call.
It's called from `app/main.py` (service="erpx-api") for the API process and
from `app/core/celery_app.py` (service="erpx-celery") for Celery workers/
beat — previously only `app/main.py` called it, which meant Celery
processes silently fell back to structlog's un-configured default renderer
(plain key=value text, no JSON, no schema fields at all) despite using the
identical `get_logger()` API. That inconsistency was a real, verified bug
(see docs/logging-architecture-proposal.md Section 1) — this file now
makes both entrypoints produce the exact same schema.
"""

import logging
import os
import socket
import sys

import structlog
from structlog.processors import CallsiteParameter

from app.core.config import settings

_HOSTNAME = socket.gethostname()


def _static_fields_processor(service_name: str):
    """Injects process-wide constants that never vary per request/task —
    deliberately a plain closure, not contextvars, since these describe the
    process itself, not a request in flight."""

    def processor(logger, method_name, event_dict):
        event_dict.setdefault("service", service_name)
        event_dict.setdefault("environment", settings.ENVIRONMENT)
        event_dict.setdefault("hostname", _HOSTNAME)

        # Populated once a future deployment injects these via the
        # Kubernetes Downward API (POD_NAME/POD_NAMESPACE env vars) — that
        # manifest change is deferred to the Loki/Fluent Bit implementation
        # itself (out of scope here: no K8s resources are touched by this
        # change). Genuinely null until then, not a placeholder value.
        pod_name = os.environ.get("POD_NAME")
        pod_namespace = os.environ.get("POD_NAMESPACE")
        if pod_name or pod_namespace:
            event_dict.setdefault(
                "pod_container_metadata",
                {"pod_name": pod_name, "pod_namespace": pod_namespace, "hostname": _HOSTNAME},
            )
        else:
            event_dict.setdefault("pod_container_metadata", None)
        return event_dict

    return processor


def _rename_exception_key(logger, method_name, event_dict):
    """`structlog.processors.format_exc_info` (already in the shared
    processor chain below) writes the formatted traceback under an
    `exception` key. Renamed to `exception_details` to match the unified
    schema's fixed key name — a one-line rename, not new exception-handling
    logic; `app/core/exception_handlers.py`'s `logger.exception(...)` calls
    are completely unaffected."""
    if "exception" in event_dict:
        event_dict["exception_details"] = event_dict.pop("exception")
    return event_dict


def configure_logging(service_name: str = "erpx-api") -> None:
    log_level = logging.DEBUG if not settings.is_production else logging.INFO

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _rename_exception_key,
        structlog.processors.CallsiteParameterAdder({CallsiteParameter.MODULE}),
        _static_fields_processor(service_name),
    ]

    if settings.is_production:
        # `message` (not structlog's default `event`) to match the unified
        # schema — applied only for the machine-parsed production path so
        # local dev console output (which uses the default `event` key
        # ConsoleRenderer already expects) is unaffected.
        renderer = [
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ]
    else:
        renderer = [structlog.dev.ConsoleRenderer(colors=True)]

    structlog.configure(
        processors=shared_processors + renderer,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    # `.bind(logger=name)` so every log line from this logger carries which
    # module created it (the unified schema's `logger` key) without every
    # individual `logger.info(...)` call site needing to pass it — `module`
    # (added by CallsiteParameterAdder above) is the complementary, more
    # granular "which file/frame actually logged this" field.
    return structlog.get_logger(name).bind(logger=name)
