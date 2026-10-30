# Production rollout plan: backup safeguards, audit fix, monitoring, Storage Manager

Status: plan only. Nothing here has been deployed. Every step that touches production needs the owner's approval first.
Written 2026-10-30 for PRs #151 (audit), #152 (backup safeguards), #153 (off-server tooling and monitor), #154 and #155
(Storage Manager backend and web).

## What each PR changes in production

| PR | Runs where | Schema change | Restarts |
|---|---|---|---|
| #153 monitor and scripts | host (systemd units under `/opt/backups/offsite`) | none | none; adds two timers |
| #151 audit fix | `erpx_api`, `erpx_celery_worker`, `erpx_celery_beat` (one shared image) | none | those three containers |
| #152 backup safeguards | the same three containers, plus `docker-compose.prod.yml` | none | those three containers |
| #154 Storage Manager backend | `erpx_api`, plus a read-only volume | **0096, applied automatically** (see below) | `erpx_api` is recreated (new volume) |
| #155 Storage Manager web | `erpx_web` image | none | `erpx_web` |

Two facts about this deployment that shape everything:

1. **`erpx_api` runs `alembic upgrade head` and the RBAC seed every time it starts** (`RUN_MIGRATIONS: "true"` in
   `docker-compose.prod.yml`, `apps/api/scripts/entrypoint.sh`). So deploying #154 *is* applying migration 0096. #151, #152
   and #153 contain no migration, so starting `erpx_api` for them changes no schema. The seed also gives the Administrator role
   the new `storage.view` permission, the same way earlier permission additions shipped.
2. **Containers only receive the variables listed in `x-backend-env`.** #152 adds `BACKUP_IN_APP_SCHEDULE_ENABLED` and
   `BACKUP_FORMAT` there (both defaulting to today's behaviour). Without that, setting the flag in `/opt/erpx/.env` would do nothing.

## Preconditions (all before step 1)

1. The first scheduled off-server backup (03:30 UTC) is green: `SHA256SUMS` present, three files, manifest, timer active.
2. `restore_verify.sh` has passed on a machine that is not production.
3. Disk room for building images. A build can need 1 to 2 GB while the old image is still kept (images are not deleted).
   With about 4 GB free, do the four-dump cleanup (about 4.45 GB) first, using `ops/offsite-backup/ssm/pentrix-op-delete-old-dumps.json`:
   registered by the account owner, run once with `Mode=verify`, and only then with `Mode=delete` after the owner's separate approval.
   See `ops/offsite-backup/ssm/README.md` for its gates, how records are handled, and the recovery assessment.
4. Record the running image IDs (the read-only health document can print them) so every rollback below is a known target.
5. Build one service at a time, `docker compose up -d --no-deps <service>`, and `docker builder prune -af` before each build,
   as in every earlier deploy on this host.

## Order

**Step 1, #153 on the host (no application restart).** Copy the files to `/opt/backups/offsite/`, the four unit files to
`/etc/systemd/system/`, `mkdir -p /opt/backups/offsite/status`, create `monitor.conf` (`ALERT_TO=support@pentrix.in`), `systemctl daemon-reload`,
enable `offsite-monitor.timer`, and replace `offsite_backup.sh` (adds the manifest step) with the new copy.
Verify: run the monitor once and receive a test alert at that address (check spam too: `pentrix.in`'s SPF record only lists
GoDaddy while ERPX sends through Gmail, and its DMARC policy is `quarantine`, so alerts could be filtered); the next 03:30 UTC run writes `manifest.json`.
Rollback: `systemctl disable --now offsite-monitor.timer` and put back the previous `offsite_backup.sh`.

**Step 2, #151 + #152 together (one backend deploy, no migration).** Build and recreate `celery_worker`, then `celery_beat`,
then `api`, one at a time. Leave `BACKUP_IN_APP_SCHEDULE_ENABLED` at its default (on).
Verify: `/api/v1/health` (it reports the database as ok); `docker exec erpx_api python -c "from app.core.config import settings as s; print(s.BACKUP_FORMAT, s.BACKUP_IN_APP_SCHEDULE_ENABLED)"`
prints `custom True`; `celery inspect ping` pongs; beat's log lists `backups-trigger-daily`; all containers healthy.
The disk guard is now active: a night that would not fit is recorded as failed, with the numbers, instead of filling the disk.
Rollback: recreate the three services from the recorded previous image IDs. No schema was changed.

**Step 3, retire the in-app schedule.** After three green off-server nights and one passing restore verification: set
`BACKUP_IN_APP_SCHEDULE_ENABLED=false` in `/opt/erpx/.env`, `docker compose up -d --no-deps celery_beat` (only beat restarts).
Verify: beat's startup log no longer lists `backups-trigger-daily`; the 02:00 UTC run does not create a job.
Rollback: set `true`, recreate `celery_beat`. The manual "Trigger backup" button works throughout.

**Step 4, #154 + #155 (Storage Manager).** Needs: `/opt/backups/offsite/status` exists (step 1) and the migration approved.
Recreate `api` (applies 0096 and recreates the container with the read-only `/host-status` mount), then build `web`.
Verify: `alembic_version` is `0096`; Administration shows Storage Manager for an Administrator account, and a
platform superuser sees the Server tab with disk and Docker figures; every other business page still works.
Nothing is deleted by deploying it: deletion is a manual, typed action by a superuser, and the first real use should be on one
unused file chosen together.

## Rollback hazards

- **Do not roll `erpx_api` back to an image older than #154 while the database is at 0096.** The old image runs
  `alembic upgrade head` on start and fails with "Can't locate revision 0096". To roll back #154: first
  `docker exec erpx_api alembic downgrade 0095` (drops `storage_trash` and `storage_deletion_log`; any file already in Trash
  stays in the bucket under `.trash/`, only its record is lost), then recreate from the old image.
- Compressed (`.dump`) in-app backups must be restored with `pg_restore` 17 or newer (the API image has it). Old `.sql` backups
  still restore with `psql`; `restore_backup.py` handles both.
- The off-server backup does not depend on the application, so it keeps running through every rollback.

## What stays out of scope

Deleting the four old dumps (separate approval, with evidence), cleaning the existing 270 MB in `audit_logs`, any IAM change
(including restricting the shared role to the ERPX host), and CI: the workflow only triggers on pull requests into `main` or
`develop`, so none of these PRs ran CI. That gap is not touched here.
