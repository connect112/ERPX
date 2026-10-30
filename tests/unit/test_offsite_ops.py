"""
Tests for the off-server backup tooling in ops/offsite-backup: the watchdog's decisions, the restore comparison,
the manifest builder, and the S3 retention settings. None of these need a server, AWS, or a database.
"""

import importlib.util
import json
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[2] / "ops" / "offsite-backup"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, OPS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


monitor = _load("offsite_monitor")
verify = _load("verify_restore")
manifest = _load("make_manifest")

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
GB = 1024**3


def names(alerts):
    return {a["name"]: a["severity"] for a in alerts}


# ---- watchdog checks -------------------------------------------------------------------------------------------

def test_disk_is_quiet_when_there_is_room():
    assert monitor.evaluate_disk(20 * GB, 10 * GB) == []


def test_disk_warns_at_eighty_percent_and_is_critical_at_ninety():
    assert names(monitor.evaluate_disk(20 * GB, 3.5 * GB)) == {"disk": "warning"}   # 82% used, 3.5 GB free
    assert names(monitor.evaluate_disk(20 * GB, 1.5 * GB)) == {"disk": "critical"}  # 92% used


def test_disk_is_critical_when_little_is_free_even_below_the_percentage():
    assert names(monitor.evaluate_disk(1000 * GB, 1 * GB)) == {"disk": "critical"}


def test_offsite_backup_status_cases():
    ok = {"ok": True, "at": (NOW - timedelta(hours=9)).isoformat()}
    assert monitor.evaluate_offsite_status(ok, NOW) == []
    assert names(monitor.evaluate_offsite_status(None, NOW)) == {"offsite-backup": "critical"}
    failed = {"ok": False, "at": NOW.isoformat(), "error": "exit 2"}
    assert "exit 2" in monitor.evaluate_offsite_status(failed, NOW)[0]["message"]
    stale = {"ok": True, "at": (NOW - timedelta(hours=40)).isoformat()}
    assert names(monitor.evaluate_offsite_status(stale, NOW)) == {"offsite-backup": "critical"}


def test_s3_latest_needs_a_recent_complete_folder():
    today = date(2026, 10, 30)
    assert monitor.evaluate_s3_latest("daily/2026-10-30/", True, today) == []
    assert monitor.evaluate_s3_latest("daily/2026-10-29/", True, today) == []             # yesterday is fine
    assert names(monitor.evaluate_s3_latest("daily/2026-10-27/", True, today)) == {"s3-latest": "critical"}
    assert names(monitor.evaluate_s3_latest("daily/2026-10-30/", False, today)) == {"s3-latest": "critical"}
    assert names(monitor.evaluate_s3_latest(None, False, today)) == {"s3-latest": "critical"}


def test_inapp_backup_failure_and_age_are_warnings():
    assert monitor.evaluate_inapp_backup(("completed", (NOW - timedelta(hours=10)).isoformat()), NOW) == []
    assert names(monitor.evaluate_inapp_backup(("failed", NOW.isoformat()), NOW)) == {"inapp-backup": "warning"}
    assert names(monitor.evaluate_inapp_backup(("completed", (NOW - timedelta(hours=50)).isoformat()), NOW)) == {
        "inapp-backup": "warning"
    }


def test_inactive_timer_is_critical():
    assert monitor.evaluate_timer(True) == []
    assert names(monitor.evaluate_timer(False)) == {"timer": "critical"}


# ---- docker usage parsing ---------------------------------------------------------------------------------------

def test_docker_df_lines_are_parsed_and_noise_is_skipped():
    text = (
        '{"Type":"Images","TotalCount":"18","Size":"6.2GB","Reclaimable":"1.1GB (17%)","Active":"13"}\n'
        "WARNING: something unrelated\n"
        '{"Type":"Local Volumes","TotalCount":"5","Size":"7.4GB","Reclaimable":"0B (0%)"}\n'
    )
    rows = monitor.parse_docker_df(text)
    assert [r["Type"] for r in rows] == ["Images", "Local Volumes"]
    assert rows[0] == {"Type": "Images", "TotalCount": "18", "Size": "6.2GB", "Reclaimable": "1.1GB (17%)"}
    assert monitor.parse_docker_df("") == []


# ---- notification decisions ------------------------------------------------------------------------------------

def _alert(name, severity):
    return monitor.alert(name, severity, f"{name} is {severity}")


def test_a_new_problem_is_sent_once_and_not_repeated_on_the_next_run():
    sent, recovered, state = monitor.decide_notifications([_alert("disk", "warning")], {}, NOW)
    assert [a["name"] for a in sent] == ["disk"] and recovered == []
    sent, _, state = monitor.decide_notifications([_alert("disk", "warning")], state, NOW + timedelta(minutes=30))
    assert sent == []


def test_a_warning_that_becomes_critical_is_sent_again():
    _, _, state = monitor.decide_notifications([_alert("disk", "warning")], {}, NOW)
    sent, _, _ = monitor.decide_notifications([_alert("disk", "critical")], state, NOW + timedelta(minutes=30))
    assert [a["severity"] for a in sent] == ["critical"]


def test_a_critical_problem_is_repeated_after_a_day_but_a_warning_is_not():
    _, _, state = monitor.decide_notifications([_alert("disk", "critical"), _alert("inapp-backup", "warning")], {}, NOW)
    later = NOW + timedelta(hours=25)
    sent, _, _ = monitor.decide_notifications(
        [_alert("disk", "critical"), _alert("inapp-backup", "warning")], state, later
    )
    assert [a["name"] for a in sent] == ["disk"]


def test_a_cleared_problem_is_reported_as_recovered():
    _, _, state = monitor.decide_notifications([_alert("disk", "critical")], {}, NOW)
    sent, recovered, new_state = monitor.decide_notifications([], state, NOW + timedelta(hours=1))
    assert sent == [] and recovered == ["disk"] and new_state == {}


# ---- restore comparison ----------------------------------------------------------------------------------------

EXPECTED = {"alembic": "0095", "rows": {"users": 120, "audit_logs": 12000, "empty_table": 0}}


def test_matching_restore_has_no_problems():
    rows = {"users": 120, "audit_logs": 11984, "empty_table": 0}   # audit_logs: 16 rows from after the snapshot
    assert verify.compare(EXPECTED, "0095", rows) == []


def test_restore_problems_are_all_reported():
    rows = {"users": 0, "audit_logs": 9000, "extra": 3}
    problems = " | ".join(verify.compare(EXPECTED, "0094", rows))
    assert "migration version" in problems
    assert "users: manifest has 120 rows, restore has none" in problems
    assert "audit_logs: manifest 12000 rows, restore 9000 rows" in problems
    assert "table missing from the restore: empty_table" in problems
    assert "table in the restore but not in the manifest: extra" in problems


def test_small_tables_get_an_absolute_slack_not_a_percentage():
    assert verify.compare({"alembic": "1", "rows": {"t": 5}}, "1", {"t": 12}) == []
    assert verify.compare({"alembic": "1", "rows": {"t": 5}}, "1", {"t": 60}) != []


def test_parse_counts_reads_psql_output():
    alembic, rows = verify.parse_counts("alembic=0095\nusers=120\naudit_logs=12000\n")
    assert alembic == "0095" and rows == {"users": 120, "audit_logs": 12000}


# ---- manifest ---------------------------------------------------------------------------------------------------

def test_manifest_is_built_from_psql_output():
    parsed = manifest.parse_counts("alembic=c9d0e1f2a3b4\nusers=8\npayments=5\n")
    assert parsed == {"alembic": "c9d0e1f2a3b4", "table_count": 2, "rows": {"users": 8, "payments": 5}}
    built = manifest.build("2026-10-30", {"pentrix": parsed})
    assert built["stamp"] == "2026-10-30" and built["databases"]["pentrix"]["rows"]["users"] == 8


# ---- S3 retention settings and policies ------------------------------------------------------------------------

def _lifecycle():
    return {rule["ID"]: rule for rule in json.loads((OPS / "aws" / "lifecycle.json").read_text())["Rules"]}


def test_lifecycle_keeps_at_least_14_daily_8_weekly_and_6_monthly_points():
    rules = _lifecycle()
    assert rules["daily-keep-14"]["Expiration"]["Days"] >= 14
    assert rules["weekly-keep-8"]["Expiration"]["Days"] >= 8 * 7
    assert rules["monthly-keep-6"]["Expiration"]["Days"] >= 6 * 30 + 1
    assert rules["daily-keep-14"]["Filter"]["Prefix"] == "daily/"
    assert rules["weekly-keep-8"]["Filter"]["Prefix"] == "weekly/"
    assert rules["monthly-keep-6"]["Filter"]["Prefix"] == "monthly/"


def test_lifecycle_cleans_up_noncurrent_versions_partial_uploads_and_delete_markers():
    rules = _lifecycle()
    for key in ("daily-keep-14", "weekly-keep-8", "monthly-keep-6"):
        assert rules[key]["NoncurrentVersionExpiration"]["NoncurrentDays"] >= 1
        assert rules[key]["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"] >= 1
    assert rules["cleanup-expired-delete-markers"]["Expiration"]["ExpiredObjectDeleteMarker"] is True


def test_the_instance_role_can_upload_and_read_but_never_delete():
    policy = json.loads((OPS / "aws" / "iam-policy-instance-role.json").read_text())
    allowed = {a for s in policy["Statement"] if s["Effect"] == "Allow" for a in s["Action"]}
    denied = {a for s in policy["Statement"] if s["Effect"] == "Deny" for a in s["Action"]}
    assert {"s3:PutObject", "s3:GetObject"} <= allowed
    assert not any("Delete" in action for action in allowed)
    assert {"s3:DeleteObject", "s3:DeleteObjectVersion", "s3:PutLifecycleConfiguration"} <= denied


def test_the_bucket_policy_refuses_unencrypted_transport():
    policy = json.loads((OPS / "aws" / "bucket-policy.json").read_text())
    statement = policy["Statement"][0]
    assert statement["Effect"] == "Deny" and statement["Condition"] == {"Bool": {"aws:SecureTransport": "false"}}


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is not installed")
@pytest.mark.parametrize("script", ["offsite_backup.sh", "restore_verify.sh", "aws/admin-setup.sh"])
def test_shell_scripts_parse(script):
    result = subprocess.run(["bash", "-n", str(OPS / script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
