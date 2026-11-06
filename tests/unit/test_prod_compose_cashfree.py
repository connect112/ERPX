"""
The production Compose file must hand every CASHFREE_* setting to api, celery_worker and celery_beat (they share x-backend-env, and only
names listed there reach the containers), must leave Cashfree OFF unless /opt/erpx/.env says otherwise, and must never hold a key.
Plain text checks, so they need no YAML library and no Docker.
"""

import re
from pathlib import Path

from app.core.config import Settings

COMPOSE = (Path(__file__).resolve().parents[2] / "docker-compose.prod.yml").read_text(encoding="utf-8")


def backend_env() -> dict[str, str]:
    block = COMPOSE.split("x-backend-env: &backend-env", 1)[1].split("\nservices:", 1)[0]
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"^  ([A-Z][A-Z0-9_]*): (.*)$", block, re.MULTILINE)}


def service_block(name: str) -> str:
    """The text of one service under `services:` (two-space indent), up to the next service."""
    services = COMPOSE.split("\nservices:\n", 1)[1]
    pieces = re.split(r"^  ([a-z_]+):$", services, flags=re.MULTILINE)  # [before, name, body, name, body, ...]
    bodies = dict(zip(pieces[1::2], pieces[2::2]))
    return bodies[name]


def test_every_cashfree_setting_of_the_app_is_passed_through_and_nothing_else_cashfree_is():
    declared = {name for name in Settings.model_fields if name.startswith("CASHFREE_")}
    passed = {name for name in backend_env() if name.startswith("CASHFREE_")}
    assert declared == passed, f"missing from docker-compose.prod.yml: {sorted(declared - passed)}; not an app setting: {sorted(passed - declared)}"


def test_the_three_services_that_run_the_app_all_use_that_block_and_the_others_do_not():
    for service in ("api", "celery_worker", "celery_beat"):
        assert "<<: *backend-env" in service_block(service), f"{service} must use x-backend-env"
    for service in ("minio", "web", "student_portal", "employee_portal", "trainer_portal"):
        block = service_block(service)
        assert "CASHFREE_" not in block and "<<: *backend-env" not in block, f"{service} must not get payment settings"


def test_without_a_value_in_the_env_file_cashfree_is_off_and_live_mode_is_not_allowed():
    env = backend_env()
    assert env["CASHFREE_ENABLED"] == "${CASHFREE_ENABLED:-false}"
    assert env["CASHFREE_ALLOW_PRODUCTION"] == "${CASHFREE_ALLOW_PRODUCTION:-false}"
    assert env["CASHFREE_ENV"] == "${CASHFREE_ENV:-sandbox}"
    assert env["CASHFREE_APP_ID"] == "${CASHFREE_APP_ID:-}" and env["CASHFREE_SECRET_KEY"] == "${CASHFREE_SECRET_KEY:-}"


def test_the_defaults_in_the_file_are_the_ones_the_app_validated_with():
    env = backend_env()
    defaults = Settings.model_fields
    assert env["CASHFREE_API_VERSION"] == "${CASHFREE_API_VERSION:-" + str(defaults["CASHFREE_API_VERSION"].default) + "}"
    assert env["CASHFREE_ORDER_MINUTES"] == "${CASHFREE_ORDER_MINUTES:-" + str(defaults["CASHFREE_ORDER_MINUTES"].default) + "}"
    assert env["CASHFREE_WEBHOOK_MAX_AGE_HOURS"] == "${CASHFREE_WEBHOOK_MAX_AGE_HOURS:-" + str(defaults["CASHFREE_WEBHOOK_MAX_AGE_HOURS"].default) + "}"


def test_no_cashfree_value_in_the_file_is_anything_but_a_variable_reference():
    for name, value in backend_env().items():
        if name.startswith("CASHFREE_"):
            assert re.fullmatch(r"\$\{" + name + r":-[A-Za-z0-9._-]*\}", value), f"{name} must only reference the env file, not hold a value"
