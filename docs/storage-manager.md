# ERPX Storage Manager: design

Status: design for review. Nothing here is built yet. The goal is a graphical place inside ERPX to see every file the
platform stores, understand what is using the disk, and safely remove files that are no longer needed, by a person,
one confirmed action at a time.

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

Open questions for the owner: how long Trash should keep files before a person may purge them (proposal: 30 days
minimum), and whether non-superuser administrators may delete orphans in their own organization (proposal: yes, with
`storage.delete`).
