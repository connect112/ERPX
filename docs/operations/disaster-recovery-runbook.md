# Backup & Restore / Disaster Recovery Runbook

Covers `modules/backups` (the `pg_dump`-based backup mechanism) and
`apps/api/scripts/restore_backup.py` (the CLI restore tool). This is the
one document for both the day-to-day operational runbook and the DR
procedure — kept as a single file rather than split in two, since the two
are really the same procedure viewed at different times (routine
verification vs. a live incident).

See `docs/project-hardening-audit.md` (finding #2) for the design
rationale — in particular, why this is deliberately **CLI-only, manual,
confirmation-gated**, not a self-service API endpoint.

## What exists today

- **Automated daily backups**: `modules/backups/tasks.py`'s
  `backups.trigger_daily_backup` Celery beat task, `pg_dump`s the whole
  database and uploads the plain-SQL dump to MinIO/S3
  (`backups/{job_id}.sql`), recording a `BackupJob` row (status, size,
  SHA-256 checksum).
- **Manual/on-demand backup**: `POST /api/v1/backups` (`backups.manage`
  permission — Administrator/Super Admin only).
- **Restore**: `apps/api/scripts/restore_backup.py`. No API endpoint,
  no web UI. Run by an operator with direct database and object-storage
  credentials, with the API stopped.

**Multi-tenant scope**: this platform is multi-tenant at the row level,
not the database level (`modules/backups/models.py`'s own docstring). A
restore is a whole-database operation — it is not possible to restore a
single organization's data in isolation with the current schema.

## RTO / RPO

- **RPO (Recovery Point Objective)**: up to 24 hours with the default
  daily schedule (`crontab(hour=2, minute=0)`,
  `apps/api/app/core/celery_app.py`). Trigger a manual backup
  immediately before any planned risky operation (a schema migration, a
  bulk data change) to tighten this for that specific window.
- **RTO (Recovery Time Objective)**: dominated by `psql` replay time for
  the dump's actual data volume, plus operator time to follow this
  runbook. No benchmark number is published here — it depends entirely on
  database size, which is expected to grow substantially from today's
  near-empty state. Establish a real number via a periodic restore drill
  (see below) against a realistic data volume before relying on any RTO
  figure operationally.
- If using AWS RDS (`infrastructure/terraform/database.tf`): RDS's own
  automated backups (14-day retention, Multi-AZ failover) are the
  faster/simpler DR path for a whole-instance failure. This runbook's
  `restore_backup.py` path is for the self-hosted/Docker Compose
  deployment (no RDS behind it), or for restoring application data into a
  *different* database than the one that failed (e.g. rebuilding a
  corrupted database from a known-good dump).

## Before you start: preconditions

1. **Stop the API** (and Celery worker/beat) — or confirm nothing else is
   connected to the target database. `restore_backup.py` verifies this
   itself (refuses if `pg_stat_activity` shows other connections) but
   don't rely on that as your only check — actually stop the services:

   Docker Compose: `docker compose stop api celery_worker celery_beat`

   Kubernetes: `kubectl scale deployment erpx-api erpx-celery-worker --replicas=0 -n erpx`
   and `kubectl scale deployment erpx-celery-beat --replicas=0 -n erpx`

2. **Know your target.** The restore target is always an explicit
   `--database-url` — decide up front whether you're restoring into the
   same (now-corrupted) database, or a fresh one you'll cut over to
   afterward by updating `DATABASE_URL`/the K8s `erpx-secrets` Secret.

3. **Have the operator run `alembic upgrade head` mentally ready** for
   after the restore — a restored dump reflects the schema *at backup
   time*; if migrations have landed since, run them after the restore
   completes, same as any normal deploy.

## Running a restore

Always dry-run first:

```bash
cd apps/api
python -m scripts.restore_backup \
  --backup-job-id <uuid> \
  --database-url "postgresql://erpx:REAL_PASSWORD@target-host:5432/erpx" \
  --dry-run
```

This validates the backup (downloads it, checks size + SHA-256 + the
pg_dump format header), checks the target is reachable and either empty
or explicitly acknowledged for a wipe, and prints the exact plan — no
changes are made.

Then run for real:

```bash
python -m scripts.restore_backup \
  --backup-job-id <uuid> \
  --database-url "postgresql://erpx:REAL_PASSWORD@target-host:5432/erpx" \
  --initiated-by "your-name-or-email"
```

You'll be asked to type the target database name back to confirm. Use
`--force` only for a scripted/automated drill where that prompt can't be
answered interactively — it does not skip any of the safety checks, only
the interactive confirmation itself.

If the target database already has tables (e.g., restoring over the same
database that just failed), the script refuses unless you pass
`--yes-wipe-existing-schema` — the backups this platform produces are
plain-SQL dumps with no `--clean` directive, so replaying one against a
non-empty database fails with constraint violations rather than cleanly
replacing data. With that flag, the script takes its own safety backup of
the target's *current* state first (skippable via `--skip-safety-backup`,
not recommended), then drops and recreates the `public` schema before
replaying the dump.

**Restoring from a local file instead of a BackupJob:**
`--backup-file /path/to/downloaded.sql` (skips the database lookup and
MinIO download — useful for an air-gapped restore, or testing).
`--storage-key backups/<job-id>.sql` downloads directly by object key
without a BackupJob metadata lookup.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (including a successful dry-run) |
| 1 | Argument/usage error |
| 2 | Backup not found, or failed integrity/format verification |
| 3 | Target database safety check failed (other connections active, non-empty without `--yes-wipe-existing-schema`, or `--api-health-url` responded) |
| 4 | Confirmation declined or aborted (Ctrl-C) |
| 5 | The pre-restore safety backup itself failed — nothing destructive was attempted |
| 6 | `psql` replay failed partway through — target is now partially restored, see Rollback below |
| 7 | Unexpected/internal error — check the script's structured logs |

## If the restore fails partway (exit code 6)

The target database is now in a **partially-restored, likely
inconsistent state**. There is no "undo" for a partial SQL replay. The
only safe path is:

1. Confirm a safety backup was taken (printed in the script's output,
   and recorded in the local audit log — see below) — it was, unless you
   passed `--skip-safety-backup`.
2. Restore again from that safety backup file:
   `python -m scripts.restore_backup --backup-file <safety-backup-path> --database-url ... --yes-wipe-existing-schema --initiated-by ...`
3. If you did skip the safety backup and have no fallback, the target
   database needs to be rebuilt from the *original* backup from scratch
   (drop and recreate the database, then restore normally) rather than
   trusting anything currently in it.

## Audit trail

Every attempt (dry-run, succeeded, failed, or aborted) is appended as a
JSON line to a local audit log (default `restore_backup_audit.log` in the
current directory, override with `--audit-log-path`) — this is the
primary, always-written record, independent of target database state.

If the target database already has the `restore_attempts` table
(`apps/api/alembic/versions/0037_*.py` — i.e. you're restoring into an
already-migrated database), a best-effort secondary row is also written
there after the attempt completes, for querying restore history via SQL
later. This is never required for the restore itself to succeed.

## Verifying backups are actually restorable (recommended: quarterly)

A backup nobody has ever restored is unverified. Periodically:

1. `python -m scripts.restore_backup --backup-job-id <latest> --database-url <a genuinely disposable drill database> --dry-run` to confirm integrity checks pass.
2. Run it for real (without `--dry-run`) against that same disposable database.
3. Spot-check the restored data (row counts on a few key tables) against
   what you expect from the source at backup time.
4. Record the wall-clock time taken — this is your real RTO number, not
   an estimate.

## Sensitive data handling

`--database-url` and any other connection string are never printed or
logged in full — every log line and console message uses a redacted
`user@host:port/dbname` form (`redact_url()` in the script). The
downloaded/local dump file itself is deleted after a successful or failed
run if it was fetched from object storage (not deleted if you passed
`--backup-file` pointing at your own file — that one's yours to manage).
