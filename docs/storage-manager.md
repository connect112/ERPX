# ERPX Storage Manager: design

Status: backend built and tested (PR 1-4 below); the web UI follows. This began as a preliminary design and was then checked against the full specification (next section). The goal is a graphical place inside ERPX to see every file the
platform stores, understand what is using the disk, and safely remove files that are no longer needed, by a person,
one confirmed action at a time.

## Comparison with the full specification

The preliminary design was reviewed against the complete requirements. What was missing or different, and what changed:

| Requirement | In the preliminary design | Now |
|---|---|---|
| Administration > Storage Manager navigation | not mentioned | added to the web app's Administration group |
| Secure downloads | previews only | `GET /preview?download=true` (short-lived link or sandboxed authenticated stream) |
| File **and folder** navigation | files and filters only | virtual folders (storage > source > key folders, organization ids shown as names), breadcrumb, folder size and count |
| Destructive operations | `storage.delete` for administrators | **platform superusers only** at first; administrators can inspect, preview and see the dependency check, but every delete, restore and purge route requires a superuser. No delete permission exists to grant. |
| Trash retention | proposed 30 days | enforced: a purge is refused for anything in Trash under `STORAGE_TRASH_MIN_DAYS` (30), and nothing purges automatically |
| Dependency verification | registry check | registry **plus** a scan of every file-like column in every table, repeated on the server at deletion time |
| Duplicate detection | by size and checksum | objects by size + ETag, database-stored files by `md5` computed inside Postgres |
| Protected category | listed | enforced in the API: backups, anything under `backups/`, and every database-stored file refuse deletion |
| Docker, database and server storage | via the monitor's status file | same; the inspector also queries database and table sizes directly |
| Complete deletion audit | log table | `storage_deletion_log` (append-only, no write routes) with the evidence, reason, user, IP and request id |
| Complete backend and frontend tests | backend only | backend tests (real Postgres and MinIO) and web tests |

Deliberate limits: only an unreferenced file in object storage can be moved to Trash. A file with a live record is "in use"
and the owning module must release it first. Files stored inside the database (generated offer letters, certificate
templates, MoU files) can be browsed, previewed and downloaded but never deleted here.

## Principles (these are rules, not preferences)

1. **Files only, never records.** It deletes stored files. It never deletes a candidate, student, employee, invoice,
   ledger entry or any other business row.
2. **Deletion is manual.** No schedule, no "clean up automatically", no purge job. Every deletion is chosen by a
   person, previewed, and confirmed.
3. **Allowlist, not denylist.** A file is deletable only if its source is on a short list of deletable sources AND the
   dependency check finds nothing that needs it. Everything else is read-only. New storage added later is read-only by
   default.
4. **Trash first.** Where a deletion can be undone, it goes to Trash and can be restored. Emptying Trash is a separate
   manual step. Where it cannot be undone safely, the option is not offered.
5. **Same rules as the rest of ERPX.** Organization isolation, permissions, and an append-only audit trail.
   Whole-server information is for platform superusers only (`require_superuser()`, as `modules/backups` does).

## Where files live today (what it must browse)

| Source | Holds | Reference | Treatment |
|---|---|---|---|
| MinIO `documents` | uploaded documents | `documents.storage_key` | browse, preview, deletable when unreferenced |
| MinIO `media_assets` | media library | `media_assets.storage_key` | same |
| MinIO `internship_files` | internship materials | `internship_files.object_key` | same |
| MinIO `social_assets` | social media images/video | `social_assets.storage_key` | same |
| MinIO `backups/` | in-app database dumps | `backup_jobs.storage_key` | **protected**; browse and size only |
| MinIO, no owner row | orphans: object with no row pointing to it | none | the main deletable category |
| Database, generated files | offer letters, certificates, MoU files, reports, templates, email assets (9 `LargeBinary` columns) | the row itself | **browse and preview only**; the file is part of a business record |
| Server (superuser) | disk, Docker images/volumes/build cache, database sizes, off-server backup status | none | **read-only inspector** |

The generated documents (certificates, offer letters) are stored inside the database, not in MinIO, so they appear in
the explorer as a second backend. They are protected by default because deleting the bytes would damage a record.

## Dependency verification

For each file, the manager answers "is it still needed?" and shows the evidence, not just a verdict:

- **In use**: an active row points to it (shows which module, record and owner). Not deletable.
- **Referenced by a soft-deleted record**: the row has `deleted_at` set. Not deletable by default; allowed only with an
  extra typed confirmation, and it goes to Trash.
- **Orphan**: no row points to it. Deletable (to Trash).
- **Protected**: on the protected list (backups, anything under a protected prefix, database-stored files, configuration).
- **Duplicate**: same size and checksum as another file. Shown as a group. Only copies with no live reference are
  deletable; a copy referenced by another record is not, because that record would lose its file.
- **Large**: sorted and filtered by size. Large alone never makes a file deletable.

The check runs again on the server at the moment of deletion, not only when the page was loaded.

## Deleting

1. Tick one or many files. Only eligible ones can be ticked for deletion; the rest show why not.
2. **Impact preview**: a list of exactly what will move to Trash, total size recovered, and the evidence for each.
3. Type the confirmation (the count and the word DELETE). Superuser-only categories ask for a reason as well.
4. The server re-checks every file, copies it to `.trash/<timestamp>/<key>` in the same bucket, removes the original,
   and writes a deletion-log entry. Nothing is removed if any check fails.
5. **Trash** lists these with who, when and why. Restore puts the object back under its original key. Emptying Trash
   (permanent deletion) is its own manual action with its own confirmation; nothing empties it automatically.

Out of scope on purpose: Docker volumes, live database files, essential backups, configuration files and any file a
business record references. The UI shows them as read-only and the API refuses.

## Server inspector (read-only, superuser)

Disk total/used/free, per-database and top-table sizes (queried from Postgres), MinIO usage by source, Docker images,
volumes and build cache, in-app dumps, and the latest off-server backup (size, age, checksum file present). The API
runs in a container, so host facts come from `monitor_status.json`, which `ops/offsite-backup/offsite_monitor.py`
already writes every 30 minutes; the file is mounted into the API container read-only. The inspector never runs a
command on the host and has no delete action.

## Charts

Usage by category (application files by source, database, Docker, backups, free space), a trend of used space from the
monitor's history, and the top 10 largest files and tables.

## Data model (two new tables, hand-written migrations, next number after the highest on `master`)

- `storage_trash(id, organization_id, source, original_key, trash_key, size_bytes, checksum, content_type, filename,
  referenced_by jsonb, deleted_by_user_id, deleted_at, reason, restored_at, purged_at)`
- `storage_deletion_log(id, organization_id, action, source, object_key, size_bytes, evidence jsonb, user_id,
  ip_address, request_id, created_at)`: append-only; no update or delete endpoint exists.

## API (all under `/api/v1/storage-manager`)

`GET /files` (search, sort, filters: source, type, size, date, owner, status; paged) ·
`GET /usage` · `GET /files/{id}` (details + evidence) · `GET /files/{id}/preview` (short-lived URL or an
authenticated stream with `Content-Security-Policy: sandbox`, never HTML) · `POST /deletions/preview` ·
`POST /deletions` · `GET /trash` · `POST /trash/{id}/restore` · `POST /trash/purge` (manual) · `GET /deletion-log` ·
`GET /server` (superuser).

Permissions: `storage.view`, `storage.delete`, and superuser for the server inspector. Previews use presigned URLs from
the existing storage client or authenticated streams; both are scoped to the caller's organization.

## Touches shared files (each kept small and called out in its PR)

`apps/api/app/api/v1/router.py` (register the router), `modules/authorization/service.py` (the two permission codes),
`docker-compose.prod.yml` (read-only mount of the monitor's status file), `apps/web/src/components/nav-config.ts`.

## Delivery plan, one PR each, none deployed without approval

1. Read-only backend: registry of sources, file listing and filters, usage summary, server inspector. Tests.
2. Dependency verification, orphan and duplicate detection. Tests against real rows and real MinIO.
3. Secure previews.
4. Trash, restore, impact preview, confirmed deletion, deletion log (migrations).
5. Web UI: explorer, checkboxes, previews, charts, Trash, deletion log, server inspector.

As built: Trash keeps files at least 30 days (`STORAGE_TRASH_MIN_DAYS`) and nothing is purged automatically. Deleting,
restoring and purging are **superuser only**; Administrators (`storage.view`) can browse, preview, search, see the impact
preview, Trash and the deletion log, but cannot change anything. Opening up deletion to Administrators would be a separate,
deliberate decision.

## Deployment (see `docs/operations/2026-10-30-rollout-plan.md` for the whole release)

- Deploying this PR **is** applying migration 0096: `erpx_api` runs `alembic upgrade head` on every start. It adds two
  tables and changes nothing else. The RBAC seed gives the Administrator role `storage.view` at the same start.
- Needs `/opt/backups/offsite/status` on the host (the monitor writes `monitor_status.json` there); the API mounts it read-only.
  Without the file the Server tab says so and the rest works.
- Rollback: **first** `docker exec erpx_api alembic downgrade 0095` (drops the two tables; a file already in Trash stays in
  the bucket under `.trash/`, only its record is lost), **then** recreate the API from the previous image. An image older than
  this one cannot start while the database is at 0096.
- `tests/integration/test_storage_manager_migration.py` proves upgrade, exact rollback with rows present, and a second upgrade,
  on a throwaway database.

## Production acceptance checklist (read-only first; nothing here deletes a real file)

Run as a plain Administrator for A to D, and as a platform superuser for E and F. Tick each line; any failure means stop and roll back.

**A. Deployed correctly**
- [ ] `alembic_version` is `0096`; `storage_trash` and `storage_deletion_log` exist and are empty.
- [ ] `/api/v1/health` is healthy; web, API, worker, beat, Postgres, Redis, MinIO and Caddy all show healthy.
- [ ] Administrator sees **Storage Manager** under Administration. A non-admin role (trainer or student) does not, and a direct
      call to `/api/v1/storage-manager/files` returns 403.

**B. Browsing and search**
- [ ] Overview shows total size and counts per source, and the totals are plausible against the MinIO console.
- [ ] Files list pages, sorts by size and date, and filters by source, type, size range, date and status.
- [ ] Search finds a known file by name and the matching count is right; the header checkbox selects only the deletable files on the page.
- [ ] Only files of the Administrator's organization appear (spot-check one file from another organization is absent).

**C. Previews**
- [ ] An image, a PDF and a text/CSV file preview; a downloaded file matches its checksum.
- [ ] An HTML file opens only in the sandbox (response header `Content-Security-Policy: sandbox; default-src 'none'`): no script runs and nothing is loaded from it.

**D. Dependency checks (no deletion)**
- [ ] Open a file that is in use: the details show what references it and it is marked **in use**.
- [ ] Select an in-use file and press Delete: the impact preview lists the references and the confirm button stays disabled.
- [ ] Duplicates tab lists groups with matching checksums; a copy that a record uses is never offered for deletion, only unreferenced copies can be removed (from the Files tab).

**E. Trash and Restore (superuser, on one unreferenced file chosen together, ideally an upload made for the test)**
- [ ] Upload a new unreferenced test file; it appears as an orphan.
- [ ] Delete it, typing the confirmation phrase the dialog shows: it moves to Trash (`.trash/` in the bucket), disappears from Files, one deletion-log row is written.
- [ ] Restore it: it returns to its original key with the same checksum, and a restore row is logged.
- [ ] Trash shows the earliest purge date at least 30 days out; the purge button is disabled before then. **Do not purge.**
- [ ] An Administrator who is not a superuser sees the Trash and log but cannot delete or restore (403).

**F. Server inspector (superuser)**
- [ ] Disk, memory, Docker volume sizes and the backup status match `df -h` and the monitor's last run on the host.
- [ ] The tab is read-only: it offers no control that runs a command or deletes anything.

**G. After**
- [ ] Every other business page still opens (Dashboard, Students, Courses, Finance, Social Media, Email Studio).
- [ ] No new errors in `docker logs erpx_api --since 30m`.
