"""
CI helper: gates the backend job on `pip-audit`'s findings, but only for
Critical/High severity — never for Low/Moderate/Unknown.

Why this exists: `pip-audit`'s own JSON output (verified empirically
against this project's actual apps/api/requirements.txt) carries no
severity field at all, only `id`/`fix_versions`/`aliases`/`description` —
there is no `pip-audit --audit-level` equivalent to npm's. Its GHSA
aliases, however, resolve via the public OSV.dev API
(https://api.osv.dev/v1/vulns/{id}) to a real `database_specific.severity`
field (CRITICAL/HIGH/MODERATE/LOW) for GHSA-sourced advisories — that's
the actual source of truth this script uses, not a heuristic.

Usage (see .github/workflows/ci.yml's backend job):

    pip-audit -r apps/api/requirements.txt --format json -o pip-audit-report.json || true
    python .github/scripts/pip_audit_severity_gate.py pip-audit-report.json

The `pip-audit` invocation itself is intentionally allowed to exit
non-zero without failing the step (`|| true`) — *this* script is what
determines the job's actual pass/fail, specifically so Low/Moderate
findings are reported (see the uploaded report artifact) without
blocking the build, while Critical/High findings do block it.

Exit codes:
    0 - no Critical/High severity vulnerabilities found (Low/Moderate/
        Unknown findings, if any, are reported but do not fail the build)
    1 - at least one Critical or High severity vulnerability found
    2 - usage error (bad/missing report file)
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

OSV_VULN_URL = "https://api.osv.dev/v1/vulns/{}"
BLOCKING_SEVERITIES = {"CRITICAL", "HIGH"}
REQUEST_TIMEOUT_SECONDS = 10


def fetch_severity(vuln_id: str) -> str:
    """Returns CRITICAL/HIGH/MODERATE/LOW, or UNKNOWN if OSV has no
    `database_specific.severity` for this id (common for PYSEC-only
    entries with no linked GHSA advisory) or the lookup itself fails."""
    try:
        with urllib.request.urlopen(
            OSV_VULN_URL.format(vuln_id), timeout=REQUEST_TIMEOUT_SECONDS
        ) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"::warning::OSV lookup failed for {vuln_id}: {exc}", file=sys.stderr)
        return "UNKNOWN"

    severity = data.get("database_specific", {}).get("severity")
    return severity.upper() if severity else "UNKNOWN"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: pip_audit_severity_gate.py <pip-audit-report.json>", file=sys.stderr)
        return 2

    try:
        with open(argv[1], encoding="utf-8") as f:
            report = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read pip-audit report {argv[1]!r}: {exc}", file=sys.stderr)
        return 2

    dependencies = report.get("dependencies", [])
    findings = []  # (package, version, vuln_id, severity, fix_versions)
    severity_cache: dict[str, str] = {}

    for dep in dependencies:
        for vuln in dep.get("vulns", []):
            # Prefer a GHSA alias (reliably severity-rated on OSV) over the
            # PYSEC id pip-audit reports by default.
            ghsa_alias = next(
                (a for a in vuln.get("aliases", []) if a.startswith("GHSA-")), None
            )
            lookup_id = ghsa_alias or vuln["id"]

            if lookup_id not in severity_cache:
                severity_cache[lookup_id] = fetch_severity(lookup_id)
            severity = severity_cache[lookup_id]

            findings.append(
                (dep["name"], dep["version"], vuln["id"], severity, vuln.get("fix_versions", []))
            )

    if not findings:
        print("pip-audit: no known vulnerabilities found in apps/api/requirements.txt.")
        return 0

    print(f"pip-audit severity report ({len(findings)} finding(s)):\n")
    print(f"{'Package':<20} {'Version':<12} {'ID':<18} {'Severity':<10} Fix")
    print("-" * 80)
    blocking = []
    for name, version, vuln_id, severity, fix_versions in findings:
        fix = ", ".join(fix_versions) or "(no fix published yet)"
        print(f"{name:<20} {version:<12} {vuln_id:<18} {severity:<10} {fix}")
        if severity in BLOCKING_SEVERITIES:
            blocking.append((name, version, vuln_id, severity))

    print()
    if blocking:
        print(f"::error::{len(blocking)} Critical/High severity vulnerability(ies) found — failing the build:")
        for name, version, vuln_id, severity in blocking:
            print(f"::error::{name} {version}: {vuln_id} ({severity})")
        return 1

    print("No Critical/High severity vulnerabilities — build not blocked "
          "(Low/Moderate/Unknown findings above are informational; see the "
          "uploaded pip-audit-report.json artifact for full detail).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
