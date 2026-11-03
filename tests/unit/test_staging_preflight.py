"""
The Cashfree staging scripts (ops/staging-cashfree) must run on macOS's /bin/bash, which is bash 3.2.

1. A portability scan of preflight.sh and staging.sh: no `case` inside a command substitution (bash 3.2 mis-parses it:
   "command substitution: syntax error near unexpected token newline") and no bash-4-only features.
2. The behavioural suites under every bash available here. On a Mac that includes /bin/bash 3.2; elsewhere set
   STAGING_TEST_BASH32=/path/to/bash-3.2 to add it.
   - tests/preflight_test.sh: allowed and unexpected settings, CRLF, an existing STAGING_SUBNET without network
     recreation, kept validations, the external-network requirement.
   - tests/gate_test.sh: the staging test gate (`./staging.sh gate on|off|status`) used to test the status-check button alone.
   - tests/upgrade_test.sh: upgrading an already-running stack (occupied network with a stale Compose hash): refresh-app,
     tunnel, up and network-check never create, change or remove the network; recreate-network removes only an empty one.
3. The network declaration in compose.yml itself (static, and as the real `docker compose config` renders it).
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

KIT = Path(__file__).resolve().parents[2] / "ops" / "staging-cashfree"
SCRIPTS = [KIT / "preflight.sh", KIT / "staging.sh", KIT / "tests" / "fixture.sh", KIT / "tests" / "preflight_test.sh", KIT / "tests" / "upgrade_test.sh", KIT / "tests" / "gate_test.sh"]

BASH4_ONLY = {
    r"\bdeclare\s+-[a-zA-Z]*A": "associative arrays (declare -A)",
    r"\blocal\s+-[a-zA-Z]*[An]": "local -A / local -n",
    r"\bdeclare\s+-[a-zA-Z]*n": "namerefs (declare -n)",
    r"\$\{[A-Za-z_][A-Za-z0-9_]*(,,?|\^\^?)": "case conversion ${x,,} / ${x^^}",
    r"\$\{[A-Za-z_][A-Za-z0-9_]*@[QEPAaKk]\}": "${x@Q} transformations",
    r"\b(mapfile|readarray|coproc)\b": "mapfile / readarray / coproc",
    r"&>>": "&>> redirection",
    r"\|&": "|& pipe",
    r";;&|[^;];&": ";;& / ;& case fall-through",
    r"\[\[\s+-v\s": "[[ -v ]] (bash 4.2)",
}


def code_lines(path: Path):
    for number, line in enumerate(path.read_text().splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        yield number, re.sub(r"\s+#\s.*$", "", line)  # drop trailing comments


def portability_problems(path: Path) -> list[str]:
    problems = []
    for number, line in code_lines(path):
        if re.search(r"\$\(.*\bcase\b.*\besac\b", line):
            problems.append(f"{path.name}:{number}: case inside $( ... ) (bash 3.2 parse error)")
        for pattern, what in BASH4_ONLY.items():
            if re.search(pattern, line):
                problems.append(f"{path.name}:{number}: {what} is not in bash 3.2")
    return problems


def test_the_staging_scripts_use_only_bash_3_2_syntax():
    problems = [p for script in SCRIPTS for p in portability_problems(script)]
    assert problems == []


def test_the_portability_scan_catches_the_bug_that_broke_macos(tmp_path):
    # the allowlist line from a8fbd3c that failed on macOS bash 3.2
    broken = tmp_path / "preflight.sh"
    broken.write_text(
        "#!/usr/bin/env bash\n"
        "UNKNOWN=\"$(awk -F= '/^[A-Za-z_]*=/ {print $1}' \"$ENVF\" | while read -r k; do "
        "case \" $ALLOWED \" in *\" $k \"*) ;; *) echo \"$k\" ;; esac; done | tr '\\n' ' ')\"\n"
    )
    assert any("case inside $( ... )" in p for p in portability_problems(broken))


def available_bashes() -> list[str]:
    found = []
    for candidate in (os.environ.get("STAGING_TEST_BASH32"), "/bin/bash", shutil.which("bash")):
        if candidate and Path(candidate).exists() and os.path.realpath(candidate) not in {os.path.realpath(b) for b in found}:
            found.append(candidate)
    return found


@pytest.mark.skipif(shutil.which("git") is None, reason="the suites build a throwaway git repository")
@pytest.mark.parametrize("suite", ["preflight_test.sh", "upgrade_test.sh", "gate_test.sh"])
@pytest.mark.parametrize("bash", available_bashes())
def test_the_staging_suites_pass_under_each_available_bash(bash, suite):
    result = subprocess.run([bash, str(KIT / "tests" / suite)], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0 and " 0 failed" in result.stdout, result.stdout[-4000:] + result.stderr[-2000:]


# --- the network declaration (the Mac failure: Compose tried to rebuild an occupied network)


def compose_file() -> dict:
    return yaml.safe_load((KIT / "compose.yml").read_text())


def test_the_staging_network_is_external_so_compose_never_rebuilds_it():
    network = compose_file()["networks"]["default"]
    assert network["external"] is True
    assert network["name"] == "erpx-cf-staging_default"
    assert "ipam" not in network  # the subnet belongs to ./staging.sh (STAGING_SUBNET)


def test_every_service_uses_the_one_staging_network_and_no_fixed_container_name():
    for name, service in compose_file()["services"].items():
        assert "networks" not in service, f"{name} must stay on the default (staging) network"
        assert "container_name" not in service, f"{name} has a fixed container name"
        assert service.get("network_mode") is None, f"{name} uses network_mode"


@pytest.mark.skipif(shutil.which("docker") is None, reason="needs the docker CLI (no daemon is used)")
def test_the_real_docker_compose_renders_the_network_as_external(tmp_path):
    env = tmp_path / "staging.env"
    env.write_text(
        (KIT / "staging.env.example").read_text()
        + "\n".join(
            f"{key}=dummy-{key.lower()}"
            for key in (
                "POSTGRES_PASSWORD", "MINIO_ROOT_PASSWORD", "JWT_SECRET_KEY", "SEED_SUPERADMIN_PASSWORD", "STAGING_ADMIN_PASSWORD",
            )
        )
        + "\nSTAGING_PUBLIC_URL=https://example.trycloudflare.com\nSTAGING_SUBNET=10.253.247.0/24\n"
    )
    result = subprocess.run(
        ["docker", "compose", "--project-directory", str(KIT), "-f", str(KIT / "compose.yml"), "--env-file", str(env), "--profile", "tunnel", "config"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0 and "docker: 'compose' is not a docker command" in result.stderr:
        pytest.skip("docker compose plugin is not installed")
    assert result.returncode == 0, result.stderr[-2000:]
    rendered = yaml.safe_load(result.stdout)
    assert rendered["networks"]["default"] == {"name": "erpx-cf-staging_default", "external": True}
