"""
Unit tests for the OpenTelemetry tracing integration (finding #10, tracing).

Covers the safe-by-default disabled path and the trace↔log correlation
processor. The enabled end-to-end span tree (FastAPI → SQL → Redis children)
is exercised by a standalone trace-flow check during validation; here we keep
to fast, DB-free, global-state-free unit checks.
"""

import pytest

import app.core.tracing as tracing
from app.core.logging_config import _otel_trace_context

pytestmark = pytest.mark.unit


def test_init_tracing_is_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(tracing.settings, "OTEL_TRACING_ENABLED", False, raising=False)
    assert tracing.init_tracing("erpx-api") is False


def test_instrument_helpers_are_noops_when_disabled(monkeypatch):
    monkeypatch.setattr(tracing.settings, "OTEL_TRACING_ENABLED", False, raising=False)
    # Must not raise and must not import/instrument anything.
    tracing.instrument_fastapi_app(object())
    tracing.instrument_celery()


def test_trace_context_processor_no_active_span_is_noop():
    # No span in context → no trace_id/span_id added, event returned unchanged.
    event = {"message": "hello"}
    out = _otel_trace_context(None, "info", event)
    assert "trace_id" not in out
    assert "span_id" not in out


def test_trace_context_processor_injects_ids_for_active_span():
    from opentelemetry.sdk.trace import TracerProvider

    # A local provider (not the global one) — avoids polluting process state.
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("unit-op") as span:
        ctx = span.get_span_context()
        out = _otel_trace_context(None, "info", {"message": "in-span"})
        assert out["trace_id"] == format(ctx.trace_id, "032x")
        assert out["span_id"] == format(ctx.span_id, "016x")
        assert len(out["trace_id"]) == 32 and len(out["span_id"]) == 16
