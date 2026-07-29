"""
Unit tests for the Sentry error-tracking integration (finding #10).

No database or network access: `init_sentry` is exercised with a patched
`sentry_sdk.init` so nothing is ever actually initialized or sent, and the
`before_send` scrubber is tested as a pure function.
"""

import pytest

import app.core.observability as observability
from app.core.observability import _scrub_sensitive_data, init_sentry

pytestmark = pytest.mark.unit


def test_init_sentry_is_a_noop_when_dsn_is_empty(monkeypatch):
    """Empty DSN (the default / local-dev case) must disable Sentry without calling init."""
    monkeypatch.setattr(observability.settings, "SENTRY_DSN", "", raising=False)
    called = {"init": False}
    monkeypatch.setattr(
        observability.sentry_sdk, "init", lambda *a, **k: called.__setitem__("init", True)
    )

    assert init_sentry("erpx-api") is False
    assert called["init"] is False


def test_init_sentry_initializes_when_dsn_is_set(monkeypatch):
    """A configured DSN must initialize Sentry with PII disabled and the env resolved."""
    monkeypatch.setattr(
        observability.settings, "SENTRY_DSN", "https://public@example.ingest.sentry.io/1", raising=False
    )
    monkeypatch.setattr(observability.settings, "SENTRY_ENVIRONMENT", "", raising=False)
    monkeypatch.setattr(observability.settings, "ENVIRONMENT", "production", raising=False)
    monkeypatch.setattr(observability.settings, "SENTRY_TRACES_SAMPLE_RATE", 0.0, raising=False)

    captured = {}
    monkeypatch.setattr(observability.sentry_sdk, "init", lambda **kw: captured.update(kw))
    monkeypatch.setattr(observability.sentry_sdk, "set_tag", lambda *a, **k: None)

    assert init_sentry("erpx-api") is True
    # PII must never be sent, and the env falls back to ENVIRONMENT.
    assert captured["send_default_pii"] is False
    assert captured["environment"] == "production"
    assert captured["traces_sample_rate"] == 0.0
    assert captured["before_send"] is _scrub_sensitive_data


def test_before_send_scrubs_cookies_and_sensitive_headers():
    event = {
        "request": {
            "cookies": {"session": "super-secret"},
            "headers": {
                "Authorization": "Bearer abc.def.ghi",
                "Cookie": "session=super-secret",
                "X-API-Key": "sk_live_123",
                "User-Agent": "pytest",
            },
        }
    }

    scrubbed = _scrub_sensitive_data(event, {})

    assert "cookies" not in scrubbed["request"]
    assert scrubbed["request"]["headers"]["Authorization"] == "[Filtered]"
    assert scrubbed["request"]["headers"]["Cookie"] == "[Filtered]"
    assert scrubbed["request"]["headers"]["X-API-Key"] == "[Filtered]"
    # Non-sensitive headers are preserved.
    assert scrubbed["request"]["headers"]["User-Agent"] == "pytest"


def test_before_send_tolerates_events_without_a_request():
    # Process-level (non-HTTP) exceptions have no `request` key — must not raise.
    event = {"exception": {"values": []}}
    assert _scrub_sensitive_data(event, {}) is event
