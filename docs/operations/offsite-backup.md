# Off-server backup (ERPX + Pentrix)

Daily, compressed, checksummed copies of both databases and the MinIO uploads go to a private S3 bucket. This
replaces "the only backup lives on the same disk as the data". Files: `ops/offsite-backup/`.

## What runs where

| Piece | Where | When |
|---|---|---|
| `offsite_backup.sh` (`offsite-backup.timer`) | production host `/opt/backups/offsite/` | daily 03:30 UTC |
| `offsite_monitor.py` (`offsite-monitor.timer`) | production host | every 30 minutes, read-only |
| `restore_verify.sh` | a laptop or spare runner, never the production host | after setup, then weekly |
| `aws/` | applied once by an AWS administrator | - |

`offsite_backup.sh` streams `pg_dump -Fc` for `erpx` and `pentrix`, a tar.gz of every MinIO object except
`backups/` (`minio_export.py`, run inside `erpx_api` so credentials stay in the container), and a `manifest.json`
(migration version and per-table row counts). Nothing large is written to the host's disk. It reads every file back
from S3 and compares SHA-256, then writes `SHA256SUMS` **last**. A folder without `SHA256SUMS` did not finish and must
not be used.

Layout in the bucket: `daily/YYYY-MM-DD/`, copied server-side to `weekly/` on Sundays and `monthly/` on the 1st.
Retention is the bucket's lifecycle (`aws/lifecycle.json`): daily 15 days, weekly 57, monthly 186, one day or more
beyond 14 / 8 / 6 so day-boundary rounding never leaves fewer recovery points. The server cannot delete: its role
allows put/get only and explicitly denies delete, lifecycle and policy changes (`aws/iam-policy-instance-role.json`).

## One-time setup

1. An AWS administrator runs `aws/admin-setup.sh` (bucket, Block Public Access, SSE-S3, versioning, TLS-only policy,
   lifecycle, the instance-role policy).
2. Install on the host (as root): copy `offsite_backup.sh offsite_monitor.py alert_mail.py minio_export.py
   make_manifest.py counts.sql aws_config` to `/opt/backups/offsite/`, the four `*.service`/`*.timer` files to
   `/etc/systemd/system/`, and create `/opt/backups/offsite/monitor.conf` from `monitor.conf.example`.
3. `systemctl daemon-reload && systemctl enable --now offsite-backup.timer offsite-monitor.timer`.

## Restoring

Verify first, on a machine that is not production:

```bash
AWS_PROFILE=<read-only profile> ops/offsite-backup/restore_verify.sh          # newest complete backup
AWS_PROFILE=<read-only profile> ops/offsite-backup/restore_verify.sh 2026-10-29
```

It checks the checksums, restores both databases into a throwaway PostgreSQL 16 container, compares the migration
version and row counts with the manifest (busy tables may differ by max(25 rows, 2%); a missing table never passes),
checks every MinIO file against its recorded checksum, and removes everything afterwards.

Real disaster restore: stop the API and workers, download the folder, check `SHA256SUMS`, create an empty database,
`pg_restore -d <db> --no-owner --no-privileges --exit-on-error <db>.dump`, then re-upload the MinIO objects from
`minio-uploads.tar.gz` (`objects/<key>`, metadata in `manifest.json`). Dumps are custom format, so use `pg_restore`;
`apps/api/scripts/restore_backup.py` handles only the older plain-SQL dumps.

## Alerts

`offsite_monitor.py` emails `ALERT_TO` (through ERPX's SMTP, from inside `erpx_api`) when: disk is over 80% (warning)
or 90% / under 2 GB free (critical); the last off-server backup failed or is older than 27 hours; the newest S3 folder
is missing, more than a day old, or has no `SHA256SUMS`; the in-app backup failed or is stale; the timer is off. One
email per problem, a daily reminder for critical ones, and one when it clears. It writes `monitor_status.json` for the
Storage Manager.

## Retiring the in-app SQL dumps (plan, not yet done)

The in-app job (`backups.trigger_daily_backup`, 02:00 UTC) writes an uncompressed SQL dump to a temp file inside the
API container, then uploads it to MinIO `backups/`. That is about 1.15 GB a day on the same disk, with no retention,
and it needs twice that free while it runs. It duplicates the off-server backup, so the plan is to keep one daily
producer:

1. Run both until the off-server backup has 7 consecutive green nights, the monitor is emailing, and
   `restore_verify.sh` has passed.
2. Add a setting `BACKUP_IN_APP_SCHEDULE_ENABLED` (default on) that the beat schedule honours, then switch it off.
   The manual "Trigger backup" button stays. No code is deleted.
3. Only after that, and only with explicit approval, remove the old dumps from MinIO.
4. Update `docs/operations/disaster-recovery-runbook.md` and `docs/deployment/production-checklist.md`, which still
   describe the in-app dump as the backup.
