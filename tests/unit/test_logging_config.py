"""
Unit tests for structured logging configuration — the prerequisites for the
approved Loki/Fluent Bit architecture (docs/logging-architecture-proposal.md).

Covers: the unified JSON schema in production, the `event`/`exception` key
renames, static process-wide fields, `organization_id`/`user_id`/`request_id`
correlation via `app/core/audit_context.py`, and the Celery worker/beat
entrypoint regression (previously `configure_logging()` was never called for
`celery -A app.core.celery_app worker/beat`, so those processes silently
logged plain, un-configured text with no JSON and no schema fields at all).
"""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import structlog

from app.core import audit_context
from app.core.config import settings
from app.core.logging_config import configure_logging, get_logger

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]


def _reset_audit_context():
    """`audit_context.py`'s setters use plain module-level ContextVars
    (not structlog's own store) to feed `AuditLog` rows — see
    `set_audit_user`/`set_audit_organization`/`set_audit_request_metadata`.
    Those ContextVars are separate from `structlog.contextvars`'s store and
    `structlog.contextvars.clear_contextvars()` does not touch them. Tests
    below call these setters with throwaway UUIDs that don't correspond to
    real `users`/`organizations` rows; left unreset, a stale value can leak
    into another test's asyncio context and cause a foreign-key violation
    the moment that other test's code path writes an AuditLog row.

    Resets the underlying ContextVars directly rather than by calling the
    setters with None: the setters also call
    `structlog.contextvars.bind_contextvars(...)`, and binding a key to
    `None` leaves it present in log output as an explicit null rather than
    absent — which would itself break the "field is absent, not null" tests
    below. `structlog.contextvars.clear_contextvars()` (called separately)
    is what actually removes bound keys."""
    audit_context._user_id.set(None)
    audit_context._organization_id.set(None)
    audit_context._ip_address.set(None)
    audit_context._user_agent.set(None)
    audit_context._request_id.set(None)


@pytest.fixture(autouse=True)
def _reset_structlog_state():
    """Every test here reconfigures structlog, binds structlog contextvars,
    and/or sets audit_context's own ContextVars. Reset all of it before and
    after so tests never leak state into each other or into other test
    modules sharing this process."""
    structlog.contextvars.clear_contextvars()
    _reset_audit_context()
    yield
    structlog.contextvars.clear_contextvars()
    _reset_audit_context()
    configure_logging(service_name="erpx-api")


def _log_json_line(capsys, service_name="erpx-api", log_fn=None):
    configure_logging(service_name=service_name)
    logger = get_logger("modules.test.example")
    if log_fn is None:
        logger.info("test_event", foo="bar")
    else:
        log_fn(logger)
    last_line = capsys.readouterr().out.strip().splitlines()[-1]
    return json.loads(last_line)


def test_production_output_is_json_with_unified_schema_keys(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    entry = _log_json_line(capsys)

    for key in (
        "timestamp", "level", "message", "service", "environment",
        "hostname", "pod_container_metadata", "module", "logger",
    ):
        assert key in entry, f"missing unified schema key: {key}"

    assert entry["message"] == "test_event"
    assert entry["foo"] == "bar"
    assert entry["service"] == "erpx-api"
    assert entry["environment"] == "production"
    assert entry["logger"] == "modules.test.example"
    assert entry["level"] == "info"


def test_service_name_distinguishes_celery_from_api(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    entry = _log_json_line(capsys, service_name="erpx-celery")
    assert entry["service"] == "erpx-celery"


def test_exception_is_renamed_to_exception_details(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    def _raise_and_log(logger):
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("task_failed")

    entry = _log_json_line(capsys, log_fn=_raise_and_log)
    assert "exception_details" in entry
    assert "exception" not in entry
    assert "ValueError: boom" in entry["exception_details"]


def test_pod_container_metadata_is_none_without_downward_api_env_vars(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.delenv("POD_NAME", raising=False)
    monkeypatch.delenv("POD_NAMESPACE", raising=False)
    entry = _log_json_line(capsys)
    assert entry["pod_container_metadata"] is None


def test_pod_container_metadata_populated_from_downward_api_env_vars(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setenv("POD_NAME", "erpx-api-abc123")
    monkeypatch.setenv("POD_NAMESPACE", "erpx-prod")
    entry = _log_json_line(capsys)
    assert entry["pod_container_metadata"] == {
        "pod_name": "erpx-api-abc123",
        "pod_namespace": "erpx-prod",
        "hostname": entry["hostname"],
    }


def test_dev_mode_uses_console_renderer_not_json(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    configure_logging(service_name="erpx-api")
    get_logger("modules.test.example").info("dev_event")
    out = capsys.readouterr().out
    assert "dev_event" in out
    with pytest.raises(json.JSONDecodeError):
        json.loads(out.strip().splitlines()[-1])


def test_correlation_fields_populate_from_audit_context(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    request_id = "req-test-123"
    user_id = uuid.uuid4()
    organization_id = uuid.uuid4()

    audit_context.set_audit_request_metadata(ip_address="127.0.0.1", user_agent="pytest", request_id=request_id)
    audit_context.set_audit_user(user_id)
    audit_context.set_audit_organization(organization_id)

    entry = _log_json_line(capsys, log_fn=lambda logger: logger.info("correlated_event"))

    assert entry["request_id"] == request_id
    assert entry["user_id"] == str(user_id)
    assert entry["organization_id"] == str(organization_id)


def test_correlation_fields_absent_when_not_set(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    entry = _log_json_line(capsys)
    assert "request_id" not in entry
    assert "user_id" not in entry
    assert "organization_id" not in entry


def test_organization_id_is_null_when_request_never_resolves_one(monkeypatch, capsys):
    """Mirrors AuditLog.organization_id's own nullability: a request whose
    dependency chain never calls get_current_user_organization_id (e.g. a
    self-service student endpoint) legitimately has no organization_id in
    either AuditLog rows or logs — not a bug."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    audit_context.set_audit_user(uuid.uuid4())
    entry = _log_json_line(capsys, log_fn=lambda logger: logger.info("user_only_event"))
    assert "user_id" in entry
    assert "organization_id" not in entry


def test_get_logger_binds_logger_name(monkeypatch, capsys):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    entry = _log_json_line(capsys)
    assert entry["logger"] == "modules.test.example"


def test_celery_entrypoint_import_produces_json_schema_logs():
    """Regression test for the bug these prerequisites fix: the real
    `celery -A app.core.celery_app worker/beat` entrypoints import only
    `app.core.celery_app`, never `app.main`. Before this fix, that meant
    `configure_logging()` was never called for Celery processes at all, and
    every Celery log line fell back to structlog's un-configured default
    renderer (plain key=value text, no JSON, no schema fields). Run in a
    real subprocess to reproduce the entrypoint's actual import graph
    rather than relying on whatever structlog state earlier tests in this
    process happened to leave behind."""
    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    env["JWT_SECRET_KEY"] = "a" * 64
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT / "apps" / "api"), str(REPO_ROOT)])

    result = subprocess.run(
        [
            sys.executable, "-c",
            "import app.core.celery_app\n"
            "from app.core.logging_config import get_logger\n"
            "get_logger('modules.backups.tasks').info('celery_regression_check')\n",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    entry = json.loads(result.stdout.strip().splitlines()[-1])
    assert entry["service"] == "erpx-celery"
    assert entry["message"] == "celery_regression_check"
    assert entry["logger"] == "modules.backups.tasks"
