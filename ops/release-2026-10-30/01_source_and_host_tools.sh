#!/bin/bash
# STEP 1: move /opt/erpx to the merged commit and install the new host tooling (monitor, manifest, restore check).
# No container is touched and no application restarts. The live off-server backup is protected:
#   - the live scripts and units are copied to a dated folder first (that folder is the rollback),
#   - offsite_backup.sh is replaced (it gains the manifest step) but its timer and service units are NOT,
#   - aws_config and an existing monitor.conf are never overwritten.
# Paste into Run Command > AWS-RunShellScript on i-0054474b85332980a only, after setting SHA on the next line.
SHA=PASTE_THE_40_CHARACTER_MERGE_COMMIT_HERE
set -euo pipefail

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "SHA is not set to a 40-character commit id; nothing was done"; exit 2; }
cd /opt/erpx
echo "disk:"; df -h / | tail -1
test -z "$(git status --porcelain --untracked-files=no)" || { echo "tracked local changes in /opt/erpx; stopping"; git status --short | head; exit 2; }

echo "== source: $(git rev-parse --short HEAD) -> ${SHA:0:7}"
git fetch origin master
test "$(git cat-file -t "$SHA")" = commit
git merge --ff-only "$SHA"
test "$(git rev-parse HEAD)" = "$SHA"
git log -1 --format='now at %h %s'

S=/opt/erpx/ops/offsite-backup
D=/opt/backups/offsite
TS=$(date -u +%Y%m%dT%H%M%SZ)
PRE=$D/pre-release-$TS
mkdir -p "$PRE"
cp -p "$D"/*.sh "$D"/*.py "$D"/*.sql "$D"/aws_config "$PRE"/ 2>/dev/null || true
cp -p "$D"/monitor.conf "$PRE"/ 2>/dev/null || true
cp -p /etc/systemd/system/offsite-*.service /etc/systemd/system/offsite-*.timer "$PRE"/ 2>/dev/null || true
echo "previous host files saved in $PRE ($(ls "$PRE" | wc -l) files)"; echo "$PRE" > /opt/backups/pre-release-host-dir.txt

echo "== syntax check before installing anything"
for f in offsite_backup.sh restore_verify.sh; do bash -n "$S/$f"; done
for f in offsite_monitor.py alert_mail.py make_manifest.py minio_export.py verify_minio_tar.py verify_restore.py; do
  python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$S/$f"
done
echo "syntax ok"

echo "== install scripts (root:root, not world-writable)"
mkdir -p "$D/status"; chmod 755 "$D/status"
for f in offsite_backup.sh restore_verify.sh; do install -m 755 "$S/$f" "$D/$f"; done
for f in offsite_monitor.py alert_mail.py make_manifest.py minio_export.py verify_minio_tar.py verify_restore.py counts.sql; do install -m 644 "$S/$f" "$D/$f"; done
[ -f "$D/aws_config" ] || install -m 644 "$S/aws_config" "$D/aws_config"
[ -f "$D/monitor.conf" ] || install -m 644 "$S/monitor.conf.example" "$D/monitor.conf"
echo "monitor.conf:"; cat "$D/monitor.conf"

echo "== install only the monitor units; the live backup service and timer stay exactly as they are"
install -m 644 "$S/offsite-monitor.service" "$S/offsite-monitor.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now offsite-monitor.timer

echo "== run the monitor once so monitor_status.json exists for the Storage Manager (read only; it emails only if something is wrong)"
systemctl start offsite-monitor.service || true
sleep 3
ls -la "$D/status"; head -c 700 "$D/status/monitor_status.json"; echo

echo "== checks"
systemctl list-timers --all | grep -E 'offsite|NEXT' | cut -c1-170
systemctl is-active offsite-backup.timer offsite-monitor.timer
echo "live backup script now: $(sha256sum $D/offsite_backup.sh | cut -c1-16)  (replaced; the previous one is in $PRE)"
echo "NEXT PROOF: the 03:30 UTC run must write manifest.json and SHA256SUMS in s3://pentrix-erpx-backups-373384939117/daily/<date>/"
echo "== STEP 1 DONE. Nothing was restarted."
