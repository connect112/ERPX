# ERPX: MacBook (Apple Silicon) development handoff

Written on the Windows development machine on 2026-11-23 so that development can continue on a MacBook Pro M3 Pro with nothing undocumented left behind.
**Nothing in this document has been run on a Mac.** Every Mac command below is checked for syntax and against the repository on Windows only; the first
run on the Mac is the real test (see "Known limitations").

## 1. Where things are

| | |
|---|---|
| Repository | `https://github.com/connect112/ERPX` (private) |
| Branch | `srujan/learning-integration` |
| Pull request | [#180](https://github.com/connect112/ERPX/pull/180): **draft**, do not merge, do not deploy |
| Base of this handoff | commit `3d5e1a4` (PR #180 head, all 6 CI jobs green). The handoff commit on top of it adds this file, `scripts/mac-bootstrap.sh`, the release-safety work described in section 6 and its tests. `git log -1` on the Mac shows the exact tip. |
| Production | AWS, managed by the owner only. **No AWS or production access is needed or wanted for development.** Never copy production credentials to the Mac. |

```bash
mkdir -p ~/dev && cd ~/dev
git clone https://github.com/connect112/ERPX.git ERPX
cd ERPX
git checkout srujan/learning-integration
git log --oneline -3
```

(`gh auth login` or a GitHub credential helper is needed for the private repository. Use the owner's own sign-in; do not paste tokens anywhere.)

## 2. Install the tools (once)

```bash
xcode-select --install                       # git, compilers
brew install --cask docker                   # Docker Desktop for Mac (Apple silicon build); open it once and wait until it says "running"
brew install node@20 python@3.12 postgresql@16 openssl gh
brew link --force node@20 postgresql@16      # postgresql@16 is only for its client tools (pg_dump / pg_restore / psql); the database itself runs in Docker
npm install -g @anthropic-ai/claude-code     # Claude Code (or use the desktop app)
```

Docker Desktop: Settings > Resources: give it at least 6 GB memory (Elasticsearch, which is optional, wants more); keep "Use Rosetta" off: nothing here needs x86 emulation.
Free host ports 5432, 6379, 9000, 9001, 8000 and 5173-5177 (a Homebrew or Postgres.app PostgreSQL on 5432 must be stopped: `brew services stop postgresql@16`).

## 3. Run ERPX locally (execution order)

```bash
cd ~/dev/ERPX
bash scripts/mac-bootstrap.sh check       # tools and Docker are fine?
bash scripts/mac-bootstrap.sh env         # creates .env (random local JWT secret, local-only DB password); never overwrites an existing .env
bash scripts/mac-bootstrap.sh up          # builds the API image (arm64), starts PostgreSQL, Redis, MinIO, API, Celery worker + beat;
                                          #   the API container applies EVERY Alembic migration (to 0107) and seeds roles + the local admin before it listens
bash scripts/mac-bootstrap.sh seed        # synthetic internship/LMS demo data (fake people)
bash scripts/mac-bootstrap.sh frontends   # npm ci + the five Vite dev servers in the background
bash scripts/mac-bootstrap.sh health      # API + every frontend answer
```

`bash scripts/mac-bootstrap.sh all` runs the six steps above in sequence. `bash scripts/mac-bootstrap.sh stop` stops everything (data kept).

The script sets `COMPOSE_FILE=docker-compose.yml` on purpose: the tracked `docker-compose.override.yml` remaps PostgreSQL to host port 5434 for one Windows machine, and
`docker-compose.local.yml` pins Windows/Podman images. Neither applies on a Mac. If you run `docker compose` by hand, `export COMPOSE_FILE=docker-compose.yml` first.

### Local URLs and logins (all local, none connect to production)

| Application | URL | Notes |
|---|---|---|
| Backend API | http://localhost:8000/api/v1/health (docs: http://localhost:8000/api/docs in development) | |
| ERPX Admin Web | http://localhost:5173 | `apps/web`; Internship Management, LMS + Learning, Accounting, Receipts, Payments |
| Student Portal | http://localhost:5174 | `apps/student-portal` |
| Employee Portal | http://localhost:5175 | `apps/employee-portal` |
| Corporate Portal | http://localhost:5176 | `apps/corporate-portal` |
| Trainer Portal | http://localhost:5177 | `apps/trainer-portal` (moved to 5177 by the script: its config and the employee portal's both default to 5175) |
| MinIO console | http://localhost:9001 | user/password: `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` in `.env` |
| PostgreSQL | `localhost:5432`, db `erpx`, user `erpx` | password in `.env` (`erpx_secret` locally) |
| Redis | `localhost:6379` | |
| Elasticsearch (optional) | http://localhost:9200 | `docker compose up -d elasticsearch` (arm64 image exists; memory hungry; not needed for the tests) |

* Platform Super Admin (created by the API's seed): `admin@erpx.example.com` / `Admin@12345`. Its sidebar only shows platform items.
* For everything else test as a **plain Administrator** after `seed`: `admin.learning.e2e@example.com` / `LearnE2e123!`. Other seeded people: instructor `ila.e2e@example.com`, cohort students `asha.e2e@` / `meera.e2e@example.com`, an independent enrolee `solo.e2e@example.com` (same password). All are fake.
* Never put real student, payment or employee data into the local database.

### Migrations, tests, background services

```bash
docker compose exec api alembic upgrade head            # already done by `up`; re-run after pulling new migrations
docker compose exec api alembic current                 # expect 0107 on this branch
docker compose logs -f api celery_worker celery_beat    # background workers and scheduled tasks
bash scripts/mac-bootstrap.sh test                      # venv + scratch DB erpx_test at head + representative pytest + web typecheck/vitest
```

Full backend suite, as CI runs it (after `test` has created `.venv` and `erpx_test`):

```bash
source .venv/bin/activate
export DATABASE_URL=postgresql+asyncpg://erpx:erpx_secret@localhost:5432/erpx_test REDIS_URL=redis://localhost:6379/0 JWT_SECRET_KEY=test_secret_key_at_least_32_characters_long PYTHONPATH=$PWD
export MINIO_ENDPOINT=127.0.0.1:9000 MINIO_SECURE=false MINIO_BUCKET=erpx-ci-tests MINIO_ACCESS_KEY=erpx_minio MINIO_SECRET_KEY=<MINIO_ROOT_PASSWORD from .env>
pytest -v
```

Frontend, per app (what CI runs): `cd apps/<app> && npx tsc -b && npx eslint src && npx vitest run`.

### Payments (Cashfree sandbox)

The sandbox needs the owner's own **sandbox** credentials, which are not in the repository: `CASHFREE_ENABLED=true`, `CASHFREE_ENV=sandbox`, `CASHFREE_APP_ID`, `CASHFREE_SECRET_KEY`
(see `docs/CASHFREE_SANDBOX.md`). Put them only in your local `.env`. Without them the application and all tests run with payments disabled or mocked.
`CASHFREE_ALLOW_PRODUCTION` must stay unset locally. Webhook testing from the internet needs a tunnel you set up yourself; it is not part of the bootstrap.

## 4. Repository map

```
apps/api/          FastAPI app package, Alembic (apps/api/alembic/versions, 0001..0107), scripts (seed, seed_e2e, seed_learning_e2e), Dockerfile
modules/           backend domain modules (our_internships, learning, internship_learning, lms, examinations, accounting, payments, ...)
packages/          shared backend packages
apps/web/          ERPX Admin Web (React + Vite + Tailwind)       apps/student-portal, trainer-portal, corporate-portal, employee-portal (same stack)
apps/email-code-templates/   React Email templates (build/check scripts)
tests/             unit, api, integration, security, performance (repo root; run on the host, not in the container)
ops/               production release and operations scripts (release-0107 is this release); NEVER run these locally against production
docs/              architecture, runbooks, CLOUD_HANDOFF.md (read it), team-workflow.md
docker-compose.yml (local dev) | docker-compose.prod.yml (production; do not use locally) | .env.example (template) | scripts/mac-bootstrap.sh
```

Read first: `CLAUDE.md`, `docs/team-workflow.md`, `docs/CLOUD_HANDOFF.md`. House rules in short: never work on `master`; branch `<developer>/<task>`; migrations hand-written and numbered
(next free number is **0108**); no secrets in git, logs or chat; do not merge or deploy without the owner (Srujan); verify UI as a plain Administrator.

## 5. Where development stands

PR #180 ("Complete Internship and LMS Learning Integration") is a **draft**: seven shared Learning tabs (Curriculum, Enrollments, Evaluations, Projects, Discussions, Practicals, Viva)
on Internship detail and LMS Course detail over the same records, migration 0107 (additive), student and trainer portal workflows, nine security fixes, curriculum uploads, the
svglib 2.3.1 / reportlab 4.4.3 security upgrade. CI at `3d5e1a4`: backend + all five frontends green; six real-backend browser tests pass. Production is **not** at 0107; nothing has been deployed, and
nothing may be without the owner's go-ahead. Remaining moderate advisories (react-router x2, aiosmtplib, opentelemetry-api, pytest, minimatch/glob) are non-blocking follow-ups.

## 6. The four release-safety corrections (PR #180 follow-up)

An independent review of the release scripts in `ops/release-0107/` found four problems. Status at the time of this handoff:

| # | Correction | Status |
|---|---|---|
| 1 | `04_post_deploy_verify.sh` failed on a first deployment because `ops_0107_rollback_hold` does not exist before the first rollback | **Done and tested.** Missing ledger = zero active holds; an existing ledger with zero open rows passes; open holds still FAIL. |
| 2 | Failed queries silently became empty results; no nonzero exit status | **Done and tested** for `00_preflight_readonly.sh` and `04_post_deploy_verify.sh`: every mandatory query is checked, a failure is a FAIL with the database's message, `FAIL > 0` prints `RESULT: NO-GO` and exits 1, warnings stay warnings (exit 0). Read-only guarantees kept and proven (counters unchanged, only `exec`/`inspect`/`logs` reach docker). Tests: `tests/unit/test_release_0107_scripts.py` (40 pass on Windows). |
| 3 | `90_rollback_code_only.sh` moved the records before application writes were stopped | **Done and tested** (a resume-branch bug that announced but did not stop the api was found in review and fixed; a freshly started api is also stopped if private records appear; the hold now also installs a database trigger that parks private records written after it, so a late writer cannot expose them: see `ops/release-0107/REHEARSAL_REPORT_0107.md`). `90_rollback_code_only.sh` is now generated (`python ops/release-0107/wip/build_90_v2.py` from `wip/90_rollback_code_only.v2.template.sh`): preflight, guarded image, save 0107 images, **quiesce (beat, api, worker stopped; zero application DB sessions required) before the safety dump and the hold**, restore, fail-closed verify; resumable; `MODE=forward`/`verify`/`release`. Order proven by `tests/unit/test_rollback_90.py`. Found and fixed while testing: `DRY_RUN=1` hid the `+` lines of `docker stop` and then failed in verify. **Not run against real production-like compose (the stub is a stand-in for docker)**. |
| 4 | Rolling back restores the old results endpoint that lets any student read another student's results | **Done and tested.** Guards for results **and** course progress (`rollback_guard/results_routes.py`, `progress_routes.py`) are baked into a derived previous image by `90`, and verified over real HTTP against the real previous image built from `3a722a6` (`tests/unit/test_rollback_real_image.py`: the unguarded image leaks, the guarded one answers 403; own and staff still 200). |

The previous release's `GET /api/v1/lms/progress/{student_id}/course/{course_id}` had the same flaw. It is now fixed in the application too (`modules/lms/progress/routes.py`: own, superuser, or `lms.progress.manage`; tests `tests/api/test_lms_progress_access.py`) and the rollback guards it in the previous image.

## 7. Known limitations on Apple Silicon (and what is unverified)

* **Verified on a Mac (M3 Pro)**: `bash scripts/mac-bootstrap.sh test` runs the representative backend suite plus web `tsc -b`, `eslint src` and `vitest run`. Mac-specific fixes found by that run: `test` puts `.venv/bin` first on `PATH` and the dump-script tests spawn `sys.executable` (macOS has no bare `python`); `00_preflight_readonly.sh` computes the backup age with GNU `date -d` first and BSD `date -j -f` as fallback, and fails the gate on an impossible date. Remaining skips: `pymupdf` not installed, no `nginx` binary, hard-link test.
* Images: `postgres:16-alpine`, `redis:7-alpine`, `minio/minio`, `elasticsearch:8.13.4`, `python:3.12-slim`, `node:20-alpine`, `nginx:alpine` all publish arm64 builds; no `platform:` pin or Rosetta is used.
  The CI job uses `pgsty/minio@sha256:...` (a pinned digest); locally the compose file's MinIO image is used (a developer may edit it locally; do not commit that change).
* Python dependencies are pinned in `apps/api/requirements.txt` and should resolve to arm64 wheels (asyncpg, psycopg2-binary, tree-sitter 0.23.2, Pillow, reportlab). If one builds from source, `brew install libpq` and retry.
* The API container bind-mounts `apps/api`, `modules` and `packages` with `uvicorn --reload`; file watching over Docker Desktop's file sharing can be slow. Use VirtioFS (default) and, if reload lags, restart the container.
* macOS ships bash 3.2; the bootstrap avoids bash 4 features. Production is Linux: no production file was changed for the Mac (the bootstrap, this document and ops tests are additive).
* `start-erpx.ps1`, `docs/windows-runbook.md` and `docker-compose.local.yml` are Windows/Podman-only; ignore them on the Mac.
* About 14 backup/restore tests need PostgreSQL 16 client tools (`pg_dump`, `pg_restore`); without `postgresql@16` from Homebrew they fail or skip. The application is unaffected.
* The ops script tests (`tests/unit/test_release_0107_scripts.py`) need `psql` on PATH and a reachable `DATABASE_URL`; they skip otherwise.

## 8. Local-only items (not in GitHub): how to bring them across

| Item | Needed? | How |
|---|---|---|
| `.env` | generated on the Mac | `bash scripts/mac-bootstrap.sh env`. Never copy the Windows `.env`. |
| Cashfree **sandbox** keys, SMTP, AI key | only for those features | enter by hand from your password manager into the Mac `.env`; never via chat, git or logs |
| Claude Code memory (project notes from previous sessions: decisions, deployment lessons, what is open) | strongly recommended | folder on Windows: `C:\Users\sruja\.claude\projects\C--Users-sruja-Downloads-platform\memory\`. Copy it yourself (AirDrop or an encrypted USB stick), then ask Claude Code on the Mac to read it as background; it is private and some notes mention local test credentials. Do not commit it. |
| Unpushed work in other Windows worktrees (`C:\Users\sruja\dev\erpx-*`) | decide | **One branch has a commit that exists only on Windows**: worktree `erpx-docs-mod`, branch `srujan/docs-frontend-moderate-findings`, commit `f7d4c29` ("Docs: record the remaining MODERATE npm audit findings in the frontend apps"). Push it (`git -C C:\Users\sruja\dev\erpx-docs-mod push -u origin srujan/docs-frontend-moderate-findings`) if you want it. All other branches are fully on GitHub; the remaining uncommitted files elsewhere are build artifacts and the line-ending-only `ops/offsite-backup` diffs. |
| `ops/offsite-backup/ssm/archive_container.py` and `pentrix-op-archive-old-dumps.json` | **no** | line-ending-only differences on Windows, deliberately never committed |
| Docker volumes / databases / MinIO files on Windows | no | disposable test data. Local data on the Mac is rebuilt by migrations + `seed`. Do not export any database. |
| Windows-only helpers (Avast root certificate for pip inside Docker, `erpx-prev-api:test` image, scratch rehearsal harness in the temp folder) | no | The Mac does not need the certificate. The previous-version image is rebuilt from `origin/master` when the rollback rehearsal is resumed. |
| AWS credentials / production access | **never** | not needed; do not transfer |

Nothing in this repository contains a secret, a database dump or real personal data (checked before the handoff commit).

## 9. Troubleshooting

* `docker compose` talks to port 5434 or a Podman image: `export COMPOSE_FILE=docker-compose.yml`.
* Port already in use: `lsof -nP -iTCP:5432 -sTCP:LISTEN` then stop that service. The Vite servers use `--strictPort` and fail loudly instead of silently moving.
* API unhealthy: `docker compose logs --tail 80 api`. A crash loop in `entrypoint.sh` right after a pull usually means a new migration conflicts with an old local database: `docker compose down -v` then `up` (this **deletes the local data**, which is only demo data).
* `pip install` cannot find a wheel on arm64: `brew install libpq` (psycopg2/asyncpg source builds) and retry; report the package name.
* Frontend `npm ci` complains about optional native packages: use Node 20, delete `node_modules` and run `npm ci` again (platform-specific esbuild/rollup binaries are selected automatically).
* Tests skip or fail on `pg_dump`/`pg_restore`: install `postgresql@16` and make sure `pg_dump --version` says 16.
* Docker out of disk: `docker system df`; `docker builder prune`.

## 10. Continue with Claude Code on the MacBook

```bash
cd ~/dev/ERPX && claude
```

First message (copy this block):

```text
You are continuing ERPX development for the owner, Srujan, on a MacBook (Apple silicon). Repo: connect112/ERPX, branch srujan/learning-integration, draft PR #180
(do not merge, do not deploy, no AWS or production access, never run production migrations, no secrets in git/logs/chat).
Read, in order: CLAUDE.md, docs/team-workflow.md, MACBOOK_HANDOFF.md (section 5 and 6 say where we stopped), then ops/release-0107/RELEASE_CHECKLIST_0107.md.
Run `bash scripts/mac-bootstrap.sh test` first and compare with the counts in MACBOOK_HANDOFF.md. The four release-safety corrections are done; what remains is the
owner's review, the staging rehearsal of 90_rollback_code_only.sh on a real compose stack (checklist part 4.3; the rehearsal evidence is in `ops/release-0107/REHEARSAL_REPORT_0107.md`), and CI. Do not start anything else without being asked.
```
