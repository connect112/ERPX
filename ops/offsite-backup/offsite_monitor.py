#!/usr/bin/env python3
"""Storage and backup watchdog for the ERPX host. Runs every 30 minutes (offsite-monitor.timer), read-only.

It checks: disk space, that the off-server backup ran and is complete, that the in-app backup has not failed, and that
the backup timer is on. It emails when something is wrong, once per problem (plus a daily reminder for critical ones),
and says so when the problem clears. It also writes monitor_status.json, which the Storage Manager reads.

The decisions are plain functions (evaluate_*, decide_notifications) so they are tested without a server; main() only
gathers facts. Host Python is 3.9, so no new-style type syntax.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

STATE_DIR = os.environ.get("OFFSITE_DIR", "/opt/backups/offsite")
# monitor_status.json goes in its own folder so the API container can mount just that, read-only, for the Storage Manager.
STATUS_DIR = os.environ.get("OFFSITE_STATUS_DIR", os.path.join(STATE_DIR, "status"))
BUCKET = os.environ.get("OFFSITE_BUCKET", "pentrix-erpx-backups-373384939117")
WARN_PCT = int(os.environ.get("DISK_WARN_PCT", "80"))
CRIT_PCT = int(os.environ.get("DISK_CRIT_PCT", "90"))
MIN_FREE_BYTES = int(float(os.environ.get("DISK_MIN_FREE_GB", "2")) * 1024**3)
OFFSITE_MAX_AGE_HOURS = 27  # a daily job, plus slack
INAPP_MAX_AGE_HOURS = 36
REPEAT_CRITICAL_AFTER = timedelta(hours=24)

CRIT, WARN = "critical", "warning"


def alert(name, severity, message):
    return {"name": name, "severity": severity, "message": message}


def _parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def evaluate_disk(total, free):
    used_pct = round(100 * (total - free) / total) if total else 0
    gb = free / 1024**3
    if used_pct >= CRIT_PCT or free < MIN_FREE_BYTES:
        return [alert("disk", CRIT, f"Server disk is {used_pct}% full with {gb:.1f} GB free. Backups and the database "
                                    f"stop working if it fills.")]
    if used_pct >= WARN_PCT:
        return [alert("disk", WARN, f"Server disk is {used_pct}% full ({gb:.1f} GB free).")]
    return []


def evaluate_offsite_status(status, now):
    if status is None:
        return [alert("offsite-backup", CRIT, "No off-server backup status file: the backup has never run here.")]
    when = _parse_time(status.get("at"))
    if not status.get("ok"):
        return [alert("offsite-backup", CRIT, f"The last off-server backup FAILED ({status.get('error', 'unknown error')}) "
                                              f"at {status.get('at')}. Check: journalctl -u offsite-backup.service")]
    if when is None or now - when > timedelta(hours=OFFSITE_MAX_AGE_HOURS):
        return [alert("offsite-backup", CRIT, f"The last successful off-server backup is older than "
                                              f"{OFFSITE_MAX_AGE_HOURS} hours ({status.get('at')}).")]
    return []


def evaluate_s3_latest(latest_prefix, has_checksums, today):
    """latest_prefix like 'daily/2026-10-30/' (or None); the folder only counts if SHA256SUMS exists."""
    if not latest_prefix:
        return [alert("s3-latest", CRIT, "The backup bucket has no daily backup folder.")]
    day = latest_prefix.rstrip("/").split("/")[-1]
    if day < (today - timedelta(days=1)).isoformat():
        return [alert("s3-latest", CRIT, f"The newest backup in S3 is from {day}, which is more than a day old.")]
    if not has_checksums:
        return [alert("s3-latest", CRIT, f"The newest backup in S3 ({day}) has no SHA256SUMS, so it did not finish.")]
    return []


def evaluate_inapp_backup(row, now):
    """row = (status, completed_at_iso) of the newest backup_jobs row, or None."""
    if row is None:
        return [alert("inapp-backup", WARN, "The in-app backup has no job records.")]
    status, completed = row
    when = _parse_time(completed)
    if status == "failed":
        return [alert("inapp-backup", WARN, f"The in-app database backup failed at {completed}.")]
    if when is not None and now - when > timedelta(hours=INAPP_MAX_AGE_HOURS):
        return [alert("inapp-backup", WARN, f"The in-app backup last finished at {completed}, over "
                                            f"{INAPP_MAX_AGE_HOURS} hours ago.")]
    return []


def evaluate_timer(active):
    if active:
        return []
    return [alert("timer", CRIT, "offsite-backup.timer is not active: nothing will back the databases up tonight.")]


def decide_notifications(current, state, now):
    """current: list of alerts now firing. state: {name: {severity, since, last_sent}} from the previous run.
    Returns (to_send, recovered_names, new_state). Sends on a new problem, a worse severity, a daily reminder for
    critical ones, and once when a problem clears."""
    by_name = {a["name"]: a for a in current}
    new_state, to_send = {}, []
    for name, item in by_name.items():
        previous = state.get(name)
        last_sent = _parse_time(previous["last_sent"]) if previous else None
        worse = previous is not None and item["severity"] == CRIT and previous["severity"] != CRIT
        reminder = (item["severity"] == CRIT and last_sent is not None and now - last_sent >= REPEAT_CRITICAL_AFTER)
        if previous is None or worse or reminder:
            to_send.append(item)
            last_sent = now
        new_state[name] = {
            "severity": item["severity"],
            "since": previous["since"] if previous else now.isoformat(timespec="seconds"),
            "last_sent": last_sent.isoformat(timespec="seconds") if last_sent else None,
        }
    recovered = sorted(name for name in state if name not in by_name)
    return to_send, recovered, new_state


# ---- gathering facts (the only part that touches the host) ------------------------------------------------------

def _run(cmd, timeout=60):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def parse_docker_df(text):
    """`docker system df --format '{{json .}}'` prints one JSON object per line; keep the fields the inspector shows."""
    rows = []
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        rows.append({key: str(item.get(key, "")) for key in ("Type", "TotalCount", "Size", "Reclaimable")})
    return rows


def _docker_df():
    result = _run(["docker", "system", "df", "--format", "{{json .}}"])
    return parse_docker_df(result.stdout) if result.returncode == 0 else []


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _latest_s3_prefix():
    out = _run(["aws", "s3", "ls", f"s3://{BUCKET}/daily/"])
    prefixes = sorted(line.split()[-1] for line in out.stdout.splitlines() if line.strip().startswith("PRE"))
    return "daily/" + prefixes[-1] if prefixes else None


def _s3_has_checksums(prefix):
    return _run(["aws", "s3api", "head-object", "--bucket", BUCKET, "--key", prefix + "SHA256SUMS"]).returncode == 0


def _inapp_backup_row():
    sql = "select status || '|' || coalesce(completed_at::text, '') from backup_jobs order by started_at desc limit 1"
    out = _run(["docker", "exec", "shared_postgres", "psql", "-U", "postgres", "-d", "erpx", "-tA", "-c", sql])
    line = out.stdout.strip()
    if out.returncode != 0 or "|" not in line:
        return None
    status, _, completed = line.partition("|")
    return status, completed.replace(" ", "T")


def gather(now):
    usage = shutil.disk_usage("/")
    alerts = evaluate_disk(usage.total, usage.free)
    alerts += evaluate_offsite_status(_read_json(os.path.join(STATE_DIR, "last_status.json")), now)
    try:
        prefix = _latest_s3_prefix()
        alerts += evaluate_s3_latest(prefix, bool(prefix) and _s3_has_checksums(prefix), now.date())
    except Exception as exc:  # noqa: BLE001 - a monitor must never die on a check; say what failed
        alerts.append(alert("s3-latest", WARN, f"Could not check the backup bucket: {exc}"))
    alerts += evaluate_inapp_backup(_inapp_backup_row(), now)
    alerts += evaluate_timer(_run(["systemctl", "is-active", "--quiet", "offsite-backup.timer"]).returncode == 0)
    return alerts, usage


def send_email(subject, body):
    to = os.environ.get("ALERT_TO", "").strip()
    if not to:
        print("ALERT_TO is not set; not emailing:", subject)
        return False
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "alert_mail.py"), encoding="utf-8") as handle:
        script = handle.read()
    result = subprocess.run(
        ["docker", "exec", "-i", "-e", f"ALERT_TO={to}", "-e", f"ALERT_SUBJECT={subject}", "-e", f"ALERT_BODY={body}",
         "erpx_api", "python", "-"],
        input=script, capture_output=True, text=True, timeout=120,
    )
    return result.returncode == 0


def main():
    now = datetime.now(timezone.utc)
    alerts, usage = gather(now)
    state = _read_json(os.path.join(STATE_DIR, "alert_state.json")) or {}
    to_send, recovered, new_state = decide_notifications(alerts, state, now)

    host = os.uname().nodename
    if to_send:
        worst = CRIT if any(a["severity"] == CRIT for a in to_send) else WARN
        lines = [f"- [{a['severity'].upper()}] {a['message']}" for a in to_send]
        sent = send_email(f"[ERPX {worst.upper()}] {len(to_send)} storage/backup problem(s) on {host}", "\n".join(lines))
        if not sent:  # keep trying next run instead of marking it delivered
            for a in to_send:
                new_state[a["name"]]["last_sent"] = state.get(a["name"], {}).get("last_sent")
    if recovered:
        send_email(f"[ERPX OK] Resolved on {host}: {', '.join(recovered)}", "These checks are healthy again: " + ", ".join(recovered))

    status = {
        "checked_at": now.isoformat(timespec="seconds"),
        "disk_total_bytes": usage.total, "disk_free_bytes": usage.free,
        "alerts": alerts,
        "docker_df": _docker_df(),
        "offsite_backup": _read_json(os.path.join(STATE_DIR, "last_status.json")),
    }
    os.makedirs(STATUS_DIR, exist_ok=True)
    os.chmod(STATUS_DIR, 0o755)
    for directory, name, payload in ((STATE_DIR, "alert_state.json", new_state), (STATUS_DIR, "monitor_status.json", status)):
        tmp = os.path.join(directory, name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=1)
        os.chmod(tmp, 0o644)
        os.replace(tmp, os.path.join(directory, name))
    print(f"{len(alerts)} problem(s):", "; ".join(a["name"] for a in alerts) or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
