# ERPX cloud handoff (written 2026-10-30)

Read this first, then `CLAUDE.md` and `docs/team-workflow.md`. It lets a new session continue from GitHub without repeating the investigations
below. **No secrets are in this file; never add any.** The owner is Srujan (GIR Technologies); he approves every merge and every production change.

## 1. Where the code is

| Item | Value |
|---|---|
| Repository | `connect112/ERPX`, default branch `master` |
| Release commit (merge of #157, 2026-10-30) | `28b5b642f3b1027695e4fcff7861a703337c8a37` |
| This handoff | added on top of that commit by the PR that carries this file; run `git log -1 origin/master` for the exact current SHA |
| Alembic head on `master` | `0096` (Storage Manager). Production database was at `0095` when this was written (see section 6) |
| Merged in the release | #151 audit fix, #152 backup safeguards, #153 off-server backup/monitor/release scripts, #154 + #155 Storage Manager, #157 security dependency updates. All source branches still exist. |
| Not merged | #156 only (CI runs on `master`; the workflow only listed `main`/`develop`), optional. Earlier features such as Email Studio (incl. React import, migration 0090), offer letters (0088) and internship instructors (0087) are already on `master` (#143 to #146). |
| `master` protection | 1 approving review and signed commits required. PRs authored by the owner cannot be self-approved, so merging needs the owner's explicit "use `--admin`" for that merge. Use merge commits, never squash stacked PRs. Do not delete branches. |

## 2. Architecture

- **Monorepo.** Backend `apps/api` (FastAPI, SQLAlchemy 2 async, Alembic, Celery) plus feature code in top-level `modules/*` (59 modules: accounting,
  attendance, backups, crm, email_studio, hackathons, institutions, internship_learning, our_internships, pentrix_ops, social_media, storage_manager, ...)
  and shared `packages/*` (ai, email, reports, sms, storage, whatsapp). Frontends: `apps/web` (admin/staff), `student-portal`, `trainer-portal`,
  `corporate-portal`, `employee-portal`. Tests in `tests/{api,unit,security,integration,performance}`.
- **Auth.** JWT (HS256) via **PyJWT** (python-jose was removed in #157), RBAC roles/permissions seeded on every API start (`scripts/seed`), superuser flag for platform-only features.
- **Production runtime** (`docker-compose.prod.yml`, project `erpx-prod`, images built on the host from source, nothing is pulled from a registry):
  `api` (runs `alembic upgrade head` and the RBAC seed on every start), `celery_worker`, `celery_beat`, `web`, `student_portal`, `employee_portal`,
  `trainer_portal`, `minio` (`erpx_minio`, bucket `erpx-storage`), plus shared `shared_postgres` (PG 16), `shared_redis`, `shared_caddy` (TLS,
  proxies `erp.pentrix.in`), and the separate Pentrix stack in `/opt/pentrix`. 13 containers in total, all healthy at last check.
- **Pentrix integration.** Pentrix (separate repo) is the source of truth for candidates/payments/bookings; ERPX mirrors them (`modules/pentrix_ops`,
  `modules/provisioning`) and provisions students. Pentrix's own payments use Razorpay and Stripe (`docs/pentrix-payments.md`).
- **Docs worth reading:** `docs/operations/2026-10-30-rollout-plan.md`, `docs/operations/offsite-backup.md`, `docs/storage-manager.md`,
  `ops/offsite-backup/ssm/README.md`, `docs/project-hardening-audit.md`.

## 3. AWS production environment (account `373384939117`, region `us-east-1`)

- **Instances.** ERPX host `pentrix-erpx-host` `i-0054474b85332980a` (t3.small, 1.9 GB RAM, 20 GB XFS root; 58 % used after the October cleanup, 8.6 GB free).
  `pentrix-jitsi-host` `i-0729175da7cc4b621` shares the same instance role. `ats-app-server` belongs to another project: never touch it.
- **Backups bucket** `pentrix-erpx-backups-373384939117` (private, versioned, SSE-S3, TLS-only). Prefixes: `daily/` (kept 15 d), `weekly/` (57 d), `monthly/` (186 d),
  `archive/` (**no expiry**; holds the four archived October in-app dumps). The instance role `pentrix-erpx-ec2-ssm-role` can put/get only and cannot delete or change lifecycle.
- **Access model for an assistant.** No standing production access. The owner runs things in the console: **Systems Manager, Run Command, `AWS-RunShellScript`** on
  `i-0054474b85332980a` only, or the fixed documents `pentrix-op-archive-old-dumps`, `pentrix-op-delete-old-dumps` (both already used; do not run again),
  `pentrix-ro-backup-health`, `pentrix-ro-old-backups`. A read-only IAM user `pentrix-ops-readonly` (CLI profile `pentrix-ops`, sign in with `aws login`, **IAM user card,
  never root**) can list/read S3 and IAM/EC2 metadata. The AWS CLI profile named `default` belongs to another project (`coupleconnect-deploy`): never use it. Never use root for routine work.
  A cloud session has none of this: it prepares scripts and the owner runs them.
- **Alerts** go to `support@pentrix.in` via the monitor (`ops/offsite-backup/offsite_monitor.py`, every 30 min). `pentrix.in` SPF lists GoDaddy while mail goes through Gmail and DMARC is `quarantine`,
  so alerts may be filtered. Owner has not yet chosen a fix (send from the Gmail account's own domain with DKIM+DMARC, or add `include:_spf.google.com` and enable DKIM). No test alert has been sent.

## 4. Deployment process (the only supported one)

Scripts in `ops/release-2026-10-30/`, each stops at the first failure and never rolls back by itself. Replace `<SHA>` with the merged commit the owner approved.

1. `00_preflight_readonly.sh`: prints git state, image ids, `alembic current`, newest backups, live backup files. Writes nothing.
2. `01_source_and_host_tools.sh`: fast-forwards `/opt/erpx` to `<SHA>`, saves the live backup files, installs the monitor, replaces `offsite_backup.sh` (adds the manifest step), leaves the backup units alone.
3. `02a_deploy_api.sh`: disk and health gates, `pg_dump -Fc` of `erpx` to `/opt/backups/pre-release/`, saves the running image id, builds and recreates **only `api`** (applies 0096). Checkpoint C1.
4. `02b_deploy_worker_beat.sh`: `celery_worker`, then `celery_beat`. Checkpoint C2.
5. `03_deploy_web.sh`: `web` only. Checkpoint C3. Then the acceptance checklist in `docs/storage-manager.md`.
6. `99_rollback.sh` with `MODE=host|api|workers|web`. `MODE=api` runs `alembic downgrade 0095` first (an image older than 0096 cannot start on a 0096 database).

One-line form for the console (after `git fetch origin master` on the host, the scripts can be run straight from git without pasting):
`cd /opt/erpx && git fetch -q origin master && git show <SHA>:ops/release-2026-10-30/<script>.sh | sed "s/^SHA=.*/SHA=<SHA>/" | bash`
(for `99_rollback.sh` substitute `^MODE=` instead). Rules that always apply: build one service at a time with `--no-deps`; `docker builder prune -af` (build cache only) before a build is the
only prune allowed; never prune volumes or images; never touch `backups/` in MinIO or anything in S3; do not run `/opt/infra/deploy.sh` (it rebuilds more than intended).

## 5. What was done and verified

| Stage | Result |
|---|---|
| 1 Off-server backup | Live since 2026-10-29: daily 03:30 UTC `erpx.dump`, `pentrix.dump`, MinIO tar, `SHA256SUMS` written last; 30 Oct run verified OK. The manifest step and `restore_verify.sh` are in #153 and **not yet run on the server**. |
| 3 Old dump cleanup | Four in-app dumps (8-11 Oct, 4,770,955,666 bytes) archived to `archive/inapp-dumps-2026-10-08-to-11/` (gzip, `manifest.json`, `VERIFIED.json`), read back and SHA-256 checked on the host and independently from a workstation; then deleted from MinIO with a verify rehearsal first. Four `backup_jobs` rows updated (pointer cleared). Disk went from 80 % to 58 %. The 28-30 Oct dumps are intact. |
| 4 Backup safeguards, audit fix, monitoring | Merged (#151, #152, #153). Tests: backup safeguards, audit binary columns, 79 ops/SSM unit tests pass. **Not complete until the first 03:30 UTC run after deploy writes `manifest.json` and `SHA256SUMS`.** In-app schedule is still ON (default) and must stay on until three green off-server nights and a passing restore verification, with the owner's separate approval. |
| 5 Storage Manager | Merged (#154, #155). Allowlisted sources, reference scan before any deletion, Trash (>= 30 days, no auto purge), append-only log, read-only server inspector, `backups/` always protected, superuser-only delete/restore/purge. Migration 0096 up, exact rollback with rows, re-upgrade: pass. UI verified locally as Administrator and superuser. |
| Security (#157) | `pip-audit` gate 0 Critical/High (was 14); combined-tree backend suite 2050 passed + 2 load-dependent integration failures that pass alone; production image builds, `pip check` clean; web `tsc`, 177 tests, build pass. |

**Production verification results: to be filled in after the deploy** (health, authentication, Storage Manager checklist, backup preservation, next S3 backup). Do not claim the release complete before then.

## 6. Database migration status

`master` head is `0096`. Production was at `0095` before this release; the API container applies `0096` when it is recreated in step 2a. Local dev: apply with `alembic upgrade head`.
Migration numbers are assigned in order on `master`; always check `alembic heads` after merging `master` and use the next number.

## 7. Security: changed and unresolved

Changed (#157): `python-jose` -> `PyJWT` (removes `ecdsa`), `pypdf` 6.21.2, `python-dotenv` 1.2.2, `fastapi` 0.162.0 + `starlette` 1.10.0, `prometheus-fastapi-instrumentator` 8.1.0, lockfile-only `npm audit fix` in the four frontends.
FastAPI now reads an empty form value as "not sent" (handled for the hackathon `repo_url`; check any new `Form(default=None)` where `""` has meaning).

Unresolved, deliberately not hidden and no gate weakened:
- **npm audit gate is red in all four frontends:** `vitest` 3 -> 5 (Critical, with `tinypool`), `vite` 5 -> 8 (High; needs Node >= 20.19, the images use `node:20-alpine`), `zod` 3 -> 4 (High; about 175 files in `web`; needs `@hookform/resolvers` 5).
- **`web` only, no upstream fix:** `@react-email/editor`, `@tiptap/html`, `happy-dom` (High). `happy-dom` is only used by Tiptap's server-side HTML parser; ERPX uses the editor in the browser. Needs an owner decision: migrate away, or a documented, expiring exception list.
- **Backend Moderate:** `aiosmtplib` 3.0.2 (fix 5.1.2), `opentelemetry-api` 1.44.0 (1.45.1), `pytest` 8.3.3 (9.0.3).
- **CI:** `.github/workflows/ci.yml` backend job has no MinIO service and no `pg_dump`, so storage/backup tests fail there (PR #156 only fixes the missing `PYTHONPATH`). CI never gated deployment.

## 8. Backups, restore, rollback

- Layout and restore steps: `docs/operations/offsite-backup.md` (restore a day with `restore_verify.sh` on a non-production machine). Archive recovery: `aws s3 cp s3://pentrix-erpx-backups-373384939117/<archive key> - | gunzip > file.sql` and check against `manifest.json`.
- In-app backups (`modules/backups`): custom-format dumps by default (`BACKUP_FORMAT=custom`), disk guard (`BACKUP_DISK_SAFETY_FACTOR`, `BACKUP_MIN_FREE_BYTES`), `prune_backups.py` is dry-run by default, retention keep-last defaults to 0 (off).
- Rollback: `99_rollback.sh`; the pre-migration dump stays in `/opt/backups/pre-release/` (a last resort that needs the owner's approval).

## 9. Outstanding tasks (in order)

1. Deploy the release with the owner's approval of the exact commit; fill in section 5 with the real results.
2. After the first 03:30 UTC run: confirm `manifest.json` + `SHA256SUMS` in the new `daily/` folder, then call Stage 4 complete.
3. Run `restore_verify.sh` on a non-production machine; send one test alert and fix SPF/DKIM/DMARC (owner decision).
4. After three green nights and a passing restore verification: retire the in-app schedule (`BACKUP_IN_APP_SCHEDULE_ENABLED=false`, recreate `celery_beat` only), owner approval.
5. Decide the frontend toolchain migration vs exception list; bump the Moderate backend packages; give CI MinIO and a Postgres 17 client.
6. Owner-side leftovers from earlier work (not part of this release): lawyer review of the Pentrix Privacy text, and real SMTP delivery checks for offer letters and certificates.
7. **Next development: universal payments (section 10).** Do not start before the release is accepted.

## 10. Universal payment integration: requirements to implement next

Owner priority after the release: an **admin-configurable payment system, Cashfree first, extensible to Razorpay and other providers**. Confirm scope with the owner before building; the points below are the known and proposed requirements.

- **Provider abstraction** (`packages/payments` or `modules/payments`): one interface (`create_order`, `fetch_status`, `verify_webhook`/parse event, `refund`, optional `payout`), a registry keyed by provider code, adapters `cashfree` first, `razorpay` and others later without changing callers.
- **Admin configuration (UI + API, new permissions):** enable/disable per provider and per organization, test vs live mode, default provider and simple routing rules, display name, webhook URL shown for copying. Credentials are write-only: encrypted at rest (key from the environment), never returned by any API, never logged, masked in the UI.
- **Data model (new migration after 0096):** provider config, payment order, payment attempt/transaction, refund, webhook event (raw body hash, signature result, processed flag). Amounts in minor units with currency (INR default), idempotency keys, unique provider reference ids.
- **Webhooks:** raw-body signature verification, timestamp/replay protection, idempotent processing, retry-safe, async handling in Celery; reconciliation job that fetches status for stale pending orders.
- **Consumers to wire in later:** fees/payments in `our_internships` (`PaymentStatus`), `accounting` receipts/payments, and the Pentrix mirror (`modules/pentrix_ops`, which already stores provider = Razorpay or Stripe for Pentrix-originated payments).
- **Non-functional:** RBAC permissions, audit log entries for config changes, org isolation, sandbox/mocked tests only (no real keys in the repo or CI), docs, and a deployment plan with the same checkpoints as section 4.

## 11. Cloud development setup

```bash
git clone https://github.com/connect112/ERPX.git && cd ERPX
git fetch origin && git checkout -b <developer>/<task> origin/master      # never work on master
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r apps/api/requirements.txt
docker compose up -d postgres redis minio                                   # local services (see docker-compose.yml)
docker exec erpx_postgres createdb -U erpx erpx_test                        # first time only
export DATABASE_URL="postgresql+asyncpg://erpx:<local-password>@localhost:5432/erpx_test" \
       MINIO_ENDPOINT=localhost:9000 MINIO_ACCESS_KEY=<local> MINIO_SECRET_KEY=<local> MINIO_BUCKET=erpx-storage MINIO_SECURE=false \
       PYTHONPATH=$PWD
(cd apps/api && alembic upgrade head)
pytest tests/api tests/unit tests/security tests/integration -q               # full run takes 30+ minutes; run what you changed
cd apps/web && npm ci && npx tsc -b && npx eslint src && npx vitest run && npm run build
```
Local credentials come from the repo's `.env` for the developer machine (never commit or print them). Backup tests need `pg_dump`/`pg_restore` 17 on the PATH.
Verify UI changes in a browser as a plain Administrator, not Super Admin. Open PRs as drafts, list what changed and how it was verified, end commits with the co-author line. A cloud session cannot reach AWS or production:
prepare scripts and runbooks, and let the owner run them.
