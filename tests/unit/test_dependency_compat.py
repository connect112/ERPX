"""
The Celery / Kombu / redis-py stack must fit together (apps/api/scripts/check_dependency_compat.py).

The failure this guards against: requirements.txt pinned celery and redis but not kombu; Celery 5.4.0 accepts kombu >= 5.3.4 and
< 6.0, so a fresh image build picked up kombu 5.7.0, which needs redis-py >= 6.1.0 (its Redis extra says >= 6.4.0). With the pinned
redis 5.0.8 every Celery worker and Beat container died at start-up with
"kombu.exceptions.VersionMismatch: Redis transport requires redis-py versions 6.1.0 or later. You have 5.0.8" while the API stayed
healthy. pip's own checks did not notice, because the requirement lives in a Kombu extra nothing asked for.
"""

import importlib.util
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "apps" / "api" / "scripts" / "check_dependency_compat.py"
REQUIREMENTS = ROOT / "apps" / "api" / "requirements.txt"

spec = importlib.util.spec_from_file_location("check_dependency_compat", SCRIPT)
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)  # type: ignore[union-attr]

# what the metadata of the two kombu releases actually say (copied from their wheels)
KOMBU_5_7_0 = ["amqp>=5.4.2", "vine==5.1.0", 'redis<9.0.0,>=6.4.0; extra == "redis"']
KOMBU_5_6_2 = ["amqp<6.0.0,>=5.1.1", "vine==5.1.0", 'redis!=4.5.5,!=5.0.2,<6.5,>=4.5.2; extra == "redis"']
CELERY_5_4_0 = ["billiard<5.0,>=4.2.0", "kombu<6.0,>=5.3.4", "vine<6.0,>=5.1.0", 'redis!=4.5.5,<6.0.0,>=4.5.2; extra == "redis"']


def versions(**over):
    base = {"celery": "5.4.0", "kombu": "5.6.2", "amqp": "5.4.1", "billiard": "4.3.1", "vine": "5.1.0", "redis": "5.0.8"}
    return {**base, **over}


def test_kombu_5_7_0_with_redis_5_0_8_is_reported_as_incompatible():
    found = compat.problems_for(KOMBU_5_7_0, "kombu", "redis", versions(kombu="5.7.0", amqp="5.4.2"))
    assert found == ["kombu[redis] needs redis<9.0.0,>=6.4.0, but redis 5.0.8 is installed"]


def test_the_same_kombu_is_fine_with_a_new_enough_redis_py():
    assert compat.problems_for(KOMBU_5_7_0, "kombu", "redis", versions(kombu="5.7.0", amqp="5.4.2", redis="6.4.0")) == []


def test_kombu_5_6_2_works_with_the_pinned_redis_py_and_rejects_the_excluded_releases():
    assert compat.problems_for(KOMBU_5_6_2, "kombu", "redis", versions()) == []
    for bad in ("5.0.2", "4.5.5", "4.5.1", "6.5.0"):
        assert compat.problems_for(KOMBU_5_6_2, "kombu", "redis", versions(redis=bad)), bad


def test_unconditional_requirements_are_checked_too():
    assert compat.problems_for(CELERY_5_4_0, "celery", None, versions()) == []
    assert compat.problems_for(CELERY_5_4_0, "celery", None, versions(kombu="6.0.0"))  # celery 5.4.0 stops before kombu 6
    assert compat.problems_for(CELERY_5_4_0, "celery", None, versions(kombu="5.3.0"))
    assert compat.problems_for(KOMBU_5_6_2, "kombu", None, versions(vine="5.0.0"))  # kombu pins vine exactly
    assert compat.problems_for(KOMBU_5_6_2, "kombu", None, versions(amqp="5.0.0"))


def test_celerys_redis_extra_is_part_of_the_check():
    assert compat.problems_for(CELERY_5_4_0, "celery", "redis", versions()) == []
    assert compat.problems_for(CELERY_5_4_0, "celery", "redis", versions(redis="6.1.0"))  # celery 5.4.0 supports redis-py < 6


def test_a_missing_package_and_unrelated_requirements():
    assert compat.problems_for(["redis>=4"], "kombu", None, versions(redis=None)) == ["kombu needs redis>=4, which is not installed"]
    assert compat.problems_for(["click>=8", "tzdata>=2025.2"], "kombu", None, versions()) == []  # not part of this stack
    # a requirement of an extra is not enforced when the extra is not what is being checked
    assert compat.problems_for(KOMBU_5_7_0, "kombu", None, versions(kombu="5.7.0", amqp="5.4.2")) == []


def test_the_installed_messaging_stack_is_compatible():
    problems, found = compat.installed_problems()
    assert problems == [], f"{found}: {problems}"


def test_requirements_pin_the_whole_messaging_stack_exactly():
    """kombu used to float; every member of the stack must now be an exact pin, so a rebuild cannot change it."""
    pinned = {}
    for line in REQUIREMENTS.read_text().splitlines():
        match = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?==([^\s#]+)", line.strip())
        if match:
            pinned[match.group(1).lower()] = match.group(3)
    missing = [name for name in compat.STACK if name not in pinned]
    assert missing == [], f"not pinned with == in apps/api/requirements.txt: {missing}"


def test_the_pinned_stack_is_what_is_installed():
    for line in REQUIREMENTS.read_text().splitlines():
        match = re.match(r"^(celery|kombu|amqp|billiard|vine|redis)==([^\s#]+)", line.strip())
        if match:
            assert compat.installed_version(match.group(1)) == match.group(2), f"{match.group(1)}: installed != pinned"


def test_the_script_reports_a_problem_with_a_failing_exit_status(monkeypatch, capsys):
    monkeypatch.setattr(compat, "installed_problems", lambda: (["kombu[redis] needs redis<9.0.0,>=6.4.0, but redis 5.0.8 is installed"], versions()))
    assert compat.main([]) == 1
    out = capsys.readouterr().out
    assert "INCOMPATIBLE dependencies" in out and "redis 5.0.8" in out
    monkeypatch.setattr(compat, "installed_problems", lambda: ([], versions()))
    assert compat.main([]) == 0
    assert "dependency check passed" in capsys.readouterr().out


def test_a_broker_that_cannot_be_reached_is_reported_not_raised():
    problems = compat.broker_problems("redis://127.0.0.1:9/0")  # nothing listens on the discard port
    assert len(problems) == 1 and problems[0].startswith("opening a Kombu connection to the broker failed")


def reachable_redis() -> str | None:
    """A Redis to open a real Kombu connection to: REDIS_URL if something answers there (it does in CI, which runs a Redis service)."""
    import os

    url = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"
    parsed = urlparse(url)
    try:
        with socket.create_connection((parsed.hostname or "localhost", parsed.port or 6379), timeout=1):
            return url.rsplit("/", 1)[0] + "/1"
    except OSError:
        return None


def test_kombu_can_open_a_real_connection_to_redis_with_the_installed_versions():
    """Runs Kombu's own runtime guard (the one that raised VersionMismatch) against a real Redis; skipped when none is reachable."""
    url = reachable_redis()
    if url is None:
        pytest.skip("no Redis reachable (CI provides one)")
    assert compat.broker_problems(url) == []
