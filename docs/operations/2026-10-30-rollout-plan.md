# Production rollout plan: backup safeguards, audit fix, monitoring, Storage Manager

Status: plan only, finalized 2026-10-30 after an integration trial (all five PRs merged together locally: backend 2036 of 2037 tests passed,
the one failure being a Windows line-ending artifact of a test that regenerates files; web type-check, 177 unit tests and build clean;
migration 0096 upgrade, exact rollback with rows present, and re-upgrade proven on a scratch database).
Nothing here has been deployed. Every step that touches production needs the owner's approval first.
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

## Merge order (merging changes nothing in production; deploying does)

Use **"Create a merge commit"** for every PR. #155 is stacked on #154 and carries its four commits, so squashing #154 would make
#155 re-apply them and conflict; a merge commit keeps both histories intact. Order:

1. #151 audit fix, 2. #152 backup safeguards, 3. #153 off-server tooling and monitor (independent of each other).
4. #154 Storage Manager backend. Then change #155's base to `master` (`gh pr edit 155 --base master`) and merge it.
5. #156 (CI trigger and path) at any point; it touches only `.github/workflows/ci.yml`.

Files that more than one PR edits: `docker-compose.prod.yml` and `apps/api/app/core/config.py` (#152 and #154, different lines; the trial
merge is clean) and the Storage Manager files shared by #154/#155 (the stack). A trial merge of all five heads gave a single alembic
head (0096 on 0095) and every commit of every branch reachable from the result. `master` has no required status checks, so nothing blocks the merges.

Re-run this before merging: `git fetch && git merge-base --is-ancestor origin/master <branch>` for each branch (a new commit on `master`
means that branch needs one merge of `master` first).

## How the commands run

The earlier deploys used a broad deploy credential that is no longer in use. The current access is the read-only IAM user plus fixed
SSM documents the owner runs. A release therefore needs one of: (a) the owner pastes the reviewed deploy script for each step into
**Systems Manager, Run Command, `AWS-RunShellScript`** targeting only `i-0054474b85332980a` and returns the output, or (b) the owner
registers fixed `pentrix-op-deploy-*` documents (same review pattern as the archive and delete documents). (a) needs no new AWS
resource. Either way each step stops on the first failing command and prints the verification at the end.

## Final sequence (the shortest safe path; exact scripts are in `ops/release-2026-10-30/`)

Storage was recovered on 2026-10-30 (8.6 GB free), so builds are safe. The backend steps are combined: #151, #152 and #154 are one
image, so it is built once per service and the migration rides on the `api` recreate, which goes first. If it fails, nothing else has
been touched.

| Step | Script | What changes | Checkpoint (all must pass) | Rollback |
|---|---|---|---|---|
| 0 | `00_preflight_readonly.sh` | nothing (read only) | `/opt/erpx` is a clean git checkout that can fast-forward; image ids and the live backup files are recorded | none needed |
| merge | (GitHub) | `master` only | merge order above; note the merged commit id | revert is not needed: nothing is deployed |
| 1 | `01_source_and_host_tools.sh` | `/opt/erpx` fast-forwards to the commit; monitor installed; `offsite_backup.sh` replaced (adds the manifest step); backup units untouched | syntax checks pass; timers active; `monitor_status.json` written | `99_rollback.sh` `MODE=host` |
| 2a | `02a_deploy_api.sh` | pre-migration dump, then build and recreate `api`, applying 0096 | C1: `0096 (head)`, health ok, `custom True`, two new tables, `storage.view` granted, `/host-status` readable | `MODE=api` (downgrades 0095 first) |
| 2b | `02b_deploy_worker_beat.sh` | `celery_worker`, then `celery_beat` | C2: worker pong, beat running, same effective settings | `MODE=workers` |
| 3 | `03_deploy_web.sh` | `web` only | C3: healthy, bundle contains Storage Manager | `MODE=web` |
| accept | `docs/storage-manager.md` checklist | nothing | Administrator, then superuser; Trash and Restore on one test file only | n/a |
| proof | next 03:30 UTC run | nothing | `manifest.json` and `SHA256SUMS` in the new `daily/` folder; monitor quiet | `MODE=host` |

Protected throughout: the in-app dumps of 28, 29 and 30 Oct (no script touches `backups/`; Storage Manager also refuses to delete
anything under it), the S3 daily/weekly/monthly folders and the `archive/` copies (the instance role cannot delete, and no step writes there
except the normal 03:30 run), and every Pentrix container. The only prune is `docker builder prune -af` (build cache), as in every earlier deploy.
Each script stops on its first failure and never rolls back on its own.

## Preconditions (all before step 1)

1. The first scheduled off-server backup (03:30 UTC) is green: `SHA256SUMS` present, three files, manifest, timer active.
2. `restore_verify.sh` has passed on a machine that is not production.
3. Disk room for building images. A build can need 1 to 2 GB while the old image is still kept (images are not deleted).
   With about 4 GB free, do the four-dump cleanup (about 4.45 GB) first, using `ops/offsite-backup/ssm/pentrix-op-delete-old-dumps.json`:
   registered by the account owner. **Archive first** with `pentrix-op-archive-old-dumps` (`plan`, `archive`, `verify`: gzip copies in S3
   under `archive/`, read back and checked against the original checksums); the deletion document refuses to run without that verification.
   Then `Mode=verify`, and only with the owner's separate approval `Mode=delete`.
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
The full acceptance checklist (browsing, previews, permissions, Trash and Restore on one test file) is in `docs/storage-manager.md`.
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

## CI and dependency vulnerabilities (not a deployment dependency)

Production is built on the host, not by CI, and `master` has no required checks, so CI does not gate this release. It is still red, for
reasons found on 2026-10-30 from run 41011257023 of PR #156 and from local `pip-audit` / `npm audit`:

- **Backend job fails at "Run migrations"**: `ModuleNotFoundError: No module named 'modules'`, because the repository root is not on
  `PYTHONPATH`. Fixed in #156 (two lines). Whatever fails after that (the job has no MinIO or `pg_dump`) is unknown until it runs.
- **Backend `pip-audit` gate**: Critical/High in `python-jose` 3.3.0 (3 entries, 2 without upstream fix), `ecdsa` 0.19.2 (no fix; arrives
  only through `python-jose`), `pypdf` 6.19.0 (fix 6.21.2) and `starlette` 0.38.6 (fix needs 1.x, so FastAPI 0.133+).
- **Frontend `npm audit` gate**: `web` 24 findings (2 Critical, 12 High), each portal 15 (2 Critical, 8 High).

Proposed fix, kept out of these five PRs as branch `srujan/security-dependency-updates`: replace `python-jose` with `PyJWT` (three
HS256 call sites; also removes `ecdsa`), `pypdf` 6.21.2, `python-dotenv` 1.2.2, `fastapi` 0.162.0 with `starlette` 1.10.0 and
`prometheus-fastapi-instrumentator` 8.1.0 (7.x requires Starlette below 1.0), and `npm audit fix` (lockfile only) in the four apps,
which clears every in-range finding. It must pass the full backend suite before it is proposed for merge and is deployed on its own,
never inside the Storage Manager release.

Still open after that, and **not** hidden by weakening the gate: `vitest` 3 to 5 (Critical, with `tinypool`), `vite` 5 to 8 (High) and `zod` 3
to 4 (High) in all four apps. They are dev tooling except `zod`, and need a toolchain migration (Vite 8 wants Node 20.19+, `zod` 4 is
a rewrite across about 175 files in `web` and needs `@hookform/resolvers` 5). `web` also has three High findings with no upstream
fix (`@react-email/editor`, `@tiptap/html`, `happy-dom`): `happy-dom` is only used by Tiptap's server-side HTML parser, and ERPX uses the
editor in the browser. Making CI green needs the owner's decision between that migration and a documented, expiring exception list for
advisories with no upstream fix.

## What stays out of scope

Deleting the four old dumps (separate approval, with evidence), cleaning the existing 270 MB in `audit_logs`, any IAM change
(including restricting the shared role to the ERPX host), the dependency migration above, and retiring the in-app backup schedule
(step 3, which waits for three green off-server nights).

## Approvals needed to finish today (each is separate; none is implied by another)

| # | Approval | What it allows | Production effect |
|---|---|---|---|
| 1 | Stage 3 deletion (after archive is verified) | `pentrix-op-delete-old-dumps` `verify`, then `delete` of the four archived dumps | frees 4.45 GB |
| 2 | Merge #151 to #156 with merge commits, in the order above | changes `master` only | none |
| 3 | Deployment route (a) or (b) above | how the steps below run | none |
| 4 | Step 1: install monitor and manifest on the host | two timers, one script replaced, one folder | no app restart |
| 5 | Step 2: backend deploy of #151 and #152 | recreate worker, beat, api (no migration) | brief API restarts |
| 6 | Step 4: Storage Manager (#154, #155) | applies migration 0096, recreates api and web | brief restarts, two new tables |
| 7 | Alert path | send one test alert to `support@pentrix.in`, and the SPF/DKIM/DMARC choice | one email |
| 8 | Later, separately | retire the in-app schedule (step 3), and the dependency PR | not today |

Approvals 4, 5 and 6 can be given as one "deploy steps 1, 2, 4 of this plan at commit `<sha>`" once #2 is done and the merged commit is known.
