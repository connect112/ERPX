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

## Retiring the in-app SQL dumps: accelerated, evidence-based plan (not yet done)

The in-app job (`backups.trigger_daily_backup`, 02:00 UTC) writes an uncompressed SQL dump to a temp file inside the
API container, then uploads it to MinIO `backups/`. That is about 1.15 GB a night on the same disk as the databases,
with no retention, and it needs about twice that free while it runs (temp file plus the copy). It duplicates the
off-server backup, so one daily producer is enough. Waiting seven nights is not safe on this disk:

| Night (02:00 UTC) | Free before | Needs while running | Free after | Result without any change |
|---|---|---|---|---|
| 30 Oct | 5.4 GB | 2.3 GB | ~4.2 GB | ok |
| 31 Oct | ~4.2 GB | 2.3 GB | ~3.1 GB | ok |
| 1 Nov | ~3.1 GB | 2.3 GB | ~1.9 GB | ok, very tight |
| 2 Nov | ~1.9 GB | 2.3 GB | disk can reach 100% | **Postgres and the apps can fail** |

(Figures from the 29 Oct audit: 15 GB used of 20 GB, 1.15 GB per dump; they move with other activity.)

Gates, replacing "seven nights" with evidence. Each step needs your approval before it touches production.

1. **Today, no production change:** keep the off-server backup running. Review the Stage 3 report on the four oldest dumps.
   Approving their removal frees about 4.5 GB and moves the danger date from 2 Nov to about 6 Nov.
2. **After the first scheduled off-server run (03:30 UTC 30 Oct) is green:** `restore_verify.sh` passes off-box on
   that backup, the monitor is installed and a test alert has been received. This is the evidence that the new backup is
   restorable; it does not need seven nights.
3. **Deploy the safeguards branch** (`srujan/backup-safeguards`) with the schedule flag still ON. The disk guard alone
   removes the outage risk: a run that would not fit is recorded as failed with the numbers and writes nothing. With the
   table above, the guard stops the 1 Nov run (needs 3.4 GB free, has ~3.1 GB) instead of letting the disk fill.
4. **After three green off-server nights (30 Oct, 31 Oct, 1 Nov) and one passing restore verification:** set
   `BACKUP_IN_APP_SCHEDULE_ENABLED=false` and restart the beat container. No code is removed and the "Trigger backup"
   button still works. The disk stops growing.
5. **Then, with explicit approval of the exact files,** remove the old dumps from MinIO `backups/`, keeping the newest
   two until the off-server backup has a week of history.
6. Update `docs/operations/disaster-recovery-runbook.md` and `docs/deployment/production-checklist.md` (the first is done
   on `srujan/backup-safeguards`).

Rollback at any step: set the flag back to `true` and restart beat. The off-server backup is independent of the app.
