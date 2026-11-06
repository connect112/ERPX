"""
The activation guide must stay true to the repository and stay provider-neutral: every file it names exists, every container and setting
it names is real, its webhook URL is the real route, its migration check behaves as described, and it contains no host-specific address.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
GUIDE = (ROOT / "docs" / "CASHFREE_PRODUCTION_ACTIVATION.md").read_text(encoding="utf-8")
COMPOSE = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8") + (ROOT / "infrastructure" / "aws-single-host" / "docker-compose.yml").read_text(encoding="utf-8")


def test_every_repository_file_the_guide_names_exists():
    names = set(re.findall(r"`((?:ops|docs|infrastructure|tests|apps|modules)/[A-Za-z0-9_./-]+)`", GUIDE))
    names |= set(re.findall(r"(/opt/erpx/(?:ops|docs)/[A-Za-z0-9_./-]+)", GUIDE))
    assert names, "the guide should name files"
    missing = sorted(n for n in names if not (ROOT / n.replace("/opt/erpx/", "")).exists())
    assert missing == [], f"named in the guide but not in the repository: {missing}"


def test_every_container_the_guide_names_is_defined_in_the_compose_files():
    containers = set(re.findall(r"\b((?:erpx|shared)_[a-z_]+)\b", GUIDE))
    containers -= {"erpx_minio_data"}  # a volume, named in prose
    assert {"erpx_api", "erpx_celery_worker", "erpx_celery_beat", "shared_postgres"} <= containers
    unknown = sorted(c for c in containers if f"container_name: {c}" not in COMPOSE)
    assert unknown == [], f"not a container_name in the compose files: {unknown}"


def test_every_cashfree_setting_the_guide_names_is_a_real_setting():
    named = set(re.findall(r"\bCASHFREE_[A-Z_]+\b(?!\.md)", GUIDE))  # (not the file names CASHFREE_SANDBOX.md and the like)
    assert {"CASHFREE_ENABLED", "CASHFREE_ENV", "CASHFREE_ALLOW_PRODUCTION", "CASHFREE_APP_ID", "CASHFREE_SECRET_KEY", "CASHFREE_API_VERSION"} <= named
    assert sorted(n for n in named if n not in Settings.model_fields) == []


def test_the_webhook_url_in_the_guide_is_the_real_route():
    urls = set(re.findall(r"https://erp\.pentrix\.in(/api/v1/public/payments/cashfree/webhook)", GUIDE))
    assert urls == {"/api/v1/public/payments/cashfree/webhook"}
    routes = (ROOT / "modules" / "internship_onboarding" / "routes.py").read_text(encoding="utf-8")
    router = (ROOT / "apps" / "api" / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    assert '"/payments/cashfree/webhook"' in routes and 'internship_onboarding_public_router, prefix="/public"' in router
    assert f"`{Settings.model_fields['CASHFREE_API_VERSION'].default}`" in GUIDE


def test_the_guide_names_no_host_address_account_or_instance():
    assert re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", GUIDE) == []
    assert re.findall(r"\bi-[0-9a-f]{8,}\b", GUIDE) == []
    assert re.findall(r"\b\d{12}\b", GUIDE) == []  # an AWS account id


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is needed")
@pytest.mark.parametrize(
    "rev, expected",
    [("0100 (head)", "OK"), ("0101 (head)", "OK"), ("0150 (head)", "OK"), ("0097 (head)", "STOP"), ("0100", "STOP"), ("0099 (head)", "STOP"), ("Error: container is not running", "STOP"), ("", "STOP")],
)
def test_the_migration_check_in_the_guide_says_ok_only_at_0100_or_later_at_the_head(rev, expected):
    line = next(line for line in GUIDE.splitlines() if line.startswith('[[ "$rev" =='))
    done = subprocess.run([shutil.which("bash"), "-c", 'rev="$1"; ' + line, "_", rev], capture_output=True, timeout=30)
    assert done.stdout.decode().strip().endswith(f"migration check: {expected}"), (rev, done.stdout, done.stderr)
