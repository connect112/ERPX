"""
OpenTelemetry distributed tracing (Production Hardening Audit finding #10 —
the tracing/APM half; the error-aggregation half is Sentry, see
`app/core/observability.py`).

Coexists with — does not replace — the existing observability layer:
Prometheus metrics (`/metrics`) answer "how many / how fast in aggregate",
structured logs + Loki answer "what happened", Sentry answers "what broke",
and OpenTelemetry adds "which exact request, and where inside it the time
went" — a per-request span tree spanning the HTTP request, every SQL query,
every Redis command, every outbound HTTP call, and (in the worker) every
Celery task.

Behaviour is entirely environment-driven and safe by default:

- `OTEL_TRACING_ENABLED` is False by default → `init_tracing` is a complete
  no-op (no provider, no instrumentation, zero overhead). This is the
  intended local-dev / test behaviour. Tracing activates only when the flag
  is set (staging/production), mirroring how Sentry is gated on `SENTRY_DSN`.
- Spans are exported over OTLP/HTTP to `OTEL_EXPORTER_OTLP_ENDPOINT`
  (default `http://localhost:4318`, i.e. an OpenTelemetry Collector /
  Tempo / Jaeger). The `BatchSpanProcessor` exports off the request path in
  a background thread, so a slow or unreachable collector never blocks or
  fails a request.
- Sampling is `ParentBased(TraceIdRatioBased(OTEL_TRACES_SAMPLE_RATE))`
  (default 0.1 = 10%) — a child span always inherits its parent's sampling
  decision, so a trace is captured whole-or-not, and the rate is tunable per
  environment.

Trace↔log↔request-id correlation: `logging_config._otel_trace_context`
injects the active span's `trace_id`/`span_id` into every structured log
line, alongside the `request_id` the request-context middleware already
binds — so a log line, a Sentry event, and a trace can all be pivoted on the
same ids.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def _build_provider(service_name: str):
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(root=TraceIdRatioBased(settings.OTEL_TRACES_SAMPLE_RATE)),
    )
    exporter = OTLPSpanExporter(
        endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip('/')}/v1/traces"
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def init_tracing(service_name: str) -> bool:
    """
    Initialise the tracer provider and instrument the shared clients
    (SQLAlchemy, Redis, outbound HTTPX) for the given service
    (``"erpx-api"`` / ``"erpx-celery"``). Returns True if tracing was
    enabled, False if it was left off. Call once per process at startup.

    FastAPI request spans are wired separately by `instrument_fastapi_app`
    (it needs the app instance); Celery task spans by `instrument_celery`.
    """
    if not settings.OTEL_TRACING_ENABLED:
        logger.info("tracing_disabled", service=service_name, reason="OTEL_TRACING_ENABLED is false")
        return False

    from opentelemetry import trace
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    trace.set_tracer_provider(_build_provider(service_name))

    # SQLAlchemy: instrument the underlying sync engine of the app's async
    # engine so every query becomes a child span (statement + duration).
    from app.db.session import engine

    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()

    logger.info(
        "tracing_initialized",
        service=service_name,
        environment=settings.ENVIRONMENT,
        sample_rate=settings.OTEL_TRACES_SAMPLE_RATE,
        exporter_endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
    )
    return True


def instrument_fastapi_app(app) -> None:
    """Instrument a FastAPI app so each request is a root/server span
    (method, route, status, duration). No-op unless tracing is enabled."""
    if not settings.OTEL_TRACING_ENABLED:
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    # /metrics and /health* are excluded so scrape/probe traffic doesn't
    # flood the trace backend with noise.
    FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics,/health,/health/ready")


def instrument_celery() -> None:
    """Instrument Celery so each task run is a span. No-op unless enabled."""
    if not settings.OTEL_TRACING_ENABLED:
        return
    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    CeleryInstrumentor().instrument()
