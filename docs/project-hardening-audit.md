# ERPX Production Hardening Audit

Date: 2026-07-28
Scope: Docker, Kubernetes, CI/CD, Security, Performance, Monitoring, Logging,
Testing, Scalability, Disaster Recovery, Backup & Restore, Operational
Readiness.

This audit builds on, and does not repeat, `docs/project-audit.md` (the
earlier Production Readiness Audit) — items already documented there are
referenced, not re-derived. The one finding from that audit (`/health/ready`
failing on an unused Elasticsearch dependency) has since been fixed; see
`docs/architecture/health-checks.md`.

**Environment note:** no git repository existed in this working tree when
this audit was written (`git status` failed at every parent directory).
Resolved by initializing one (confirmed with you first) — see the initial
commit and the Critical fix's commit for the baseline this audit's
subsequent fixes build on.

Every finding is backed by an exact file path, verified by reading the file,
not inferred.

## Summary table

| # | Category | Finding | Severity |
|---|---|---|---|
| 1 | Security | No startup validation blocks booting in production with the default, hardcoded, source-visible JWT signing secret | **Critical** |
| 2 | Backup & Restore | No backup restore capability anywhere in the application layer | High |
| 3 | Backup & Restore | Application-level backups (`modules/backups`) are manual-only — no scheduled/automated trigger | High |
| 4 | Docker | Single-stage build ships build tooling into the runtime image; container runs as root | High — **fixed** |
| 5 | CI/CD | 3 of 4 frontend apps have no test script and are not built/tested in CI at all | High — **fixed** |
| 6 | Logging | No log shipping configured — container stdout is the only sink; logs are lost on pod eviction/restart | High |
| 7 | Operational Readiness | No documented rollback procedure for a bad deployment | Medium |
| 8 | Testing | `apps/web`'s `npm run test` (vitest) has zero test files behind it (already noted in `docs/project-audit.md`, included here for completeness) | Medium |
| 9 | Security | Global rate limiting only — auth endpoints share the same 100/min budget as read-only list endpoints (mitigated by account lockout) | Medium |
| 10 | Monitoring | Prometheus + Grafana + alert rules exist, but no distributed tracing / APM / error aggregation (Sentry, OpenTelemetry) | Medium |
| 11 | Scalability | No database read replica; all reads and writes hit the single RDS primary | Low |
| 12 | Backup & Restore | No retention/cleanup policy for application-level backup files in MinIO/S3 | Low |
| 13 | Performance | Some report aggregations fetch up to 10,000 rows and aggregate in Python rather than `GROUP BY` (already noted in `docs/deployment/production-checklist.md`) | Low |

## 1. Docker

**Finding #4 (High):** `apps/api/Dockerfile` is a single-stage build — `build-essential` and `libpq-dev` (needed only to compile Python wheels) ship into the final runtime image, and there's no `USER` directive, so the container runs as root.

- Evidence: `apps/api/Dockerfile`
- Impact: larger attack surface (compilers present at runtime), larger image (slower deploys/pulls), and a process running as root inside the container — standard CIS Docker Benchmark violation. Not an active exploit by itself, but increases blast radius if any other vulnerability in the app or a dependency is ever exploited.
- Fix: multi-stage build (`builder` stage installs + compiles, final stage copies only the venv/site-packages + app code), add a non-root `USER erpx`, keep the existing `HEALTHCHECK` (already correct).
- Effort: Small (1-2 hours) — self-contained, no application code changes.

**Status: fixed.** `apps/api/Dockerfile` rewritten as a two-stage build — a
`builder` stage with `build-essential`/`libpq-dev` that produces a venv, and
a runtime stage that copies only that venv plus app code, running as a new
non-root `erpx` system user (`groupadd`/`useradd --system`). `HEALTHCHECK`
and `CMD` unchanged.

- Files changed: `apps/api/Dockerfile`
- Tests added: none (infrastructure-only change) — verified instead by
  actually building and running the image with Docker Desktop (which
  crashed and had to be restarted mid-verification; confirmed back up
  before proceeding):
  - `docker build` succeeds cleanly, all dependencies install in the
    builder stage.
  - `docker run --rm erpx-api:hardening-test whoami` → `erpx` (confirms
    non-root).
  - Direct `docker run ... python -c "import app.main"` initially failed
    with `ModuleNotFoundError: No module named 'modules.accounting'` — this
    is **not a regression**: `docker-compose.yml` bind-mounts `./modules`
    and `./packages` from the repo root into the container at runtime
    (lines 126-128), independent of what `COPY` bakes into the image at
    build time. Rebuilt the *original* (pre-fix) Dockerfile under the
    identical `docker run` invocation and confirmed it fails identically —
    proving this is pre-existing, by-design behavior (the image has never
    been runnable via bare `docker run` without those mounts) and not
    something introduced by this fix. Re-ran with the same volume mounts
    `docker-compose.yml` provides (correcting a Git-Bash path-mangling
    issue on the container-side mount path via `MSYS_NO_PATHCONV=1`) and
    confirmed `app.main` imports successfully under realistic runtime
    conditions.
  - Image size: 973MB (original) → 540MB (hardened), a 44% reduction.
  - Full backend regression suite unaffected (this change touches no
    Python source): 211/211 passing.
- Risks: none identified. The multi-stage pattern is standard and
  well-tested; behavior parity with the original was explicitly verified
  above rather than assumed. `docker-compose.yml` itself needed no changes
  — it already targets `context: ./apps/api`, `dockerfile: Dockerfile`.

## 2. Kubernetes

Already substantially audited in `docs/project-audit.md` (real manifests, correct 3-probe setup, HPA, resource limits — verified genuine, not scaffolding). No new findings beyond what's there; the readiness-probe bug it identified is fixed.

One additional observation: `infrastructure/kubernetes/celery-deployment.yaml`'s worker Deployment has no `HorizontalPodAutoscaler` (the API Deployment does). At current scope this is reasonable — Celery task volume in this codebase is low (4 task files total) — but worth a one-line note for whoever scales this later. Not scored as a standalone finding; too speculative to size without real task-queue-depth data.

## 3. CI/CD

**Finding #5 (High):** `.github/workflows/ci.yml`'s `frontend` job only builds/tests `apps/web`. `apps/student-portal`, `apps/trainer-portal`, and `apps/corporate-portal` have no `test` script in their `package.json` and are never built, typechecked, or tested in CI.

- Evidence: `.github/workflows/ci.yml` (lines 55-77, single `frontend` job scoped to `apps/web`), `apps/student-portal/package.json`, `apps/trainer-portal/package.json`, `apps/corporate-portal/package.json` (no `test` key in any)
- Impact: a breaking change (bad import, broken build, type error) in any of the 3 other frontend apps merges to `main` and ships in a published Docker image without CI ever detecting it.
- Fix: add a matrix job (`strategy.matrix.app: [web, student-portal, trainer-portal, corporate-portal]`) or 3 additional job blocks running `npm ci && npm run build` for each.
- Effort: Small (1-2 hours) — pure CI config, no app code changes.

**Status: fixed.** `.github/workflows/ci.yml`'s `frontend` job converted to
a `strategy.matrix.app: [web, student-portal, trainer-portal,
corporate-portal]`, running install/build/test for each. Test step uses
`npm run test --if-present` since only `apps/web` has a `test` script today
(finding #8, separately tracked, not fixed here).

While verifying, found and fixed a **second, more severe bug this fix would
otherwise have shipped straight into CI**: `apps/web`'s existing `npm run
test` step doesn't just have zero test files (finding #8's description) —
it actively **crashes** (exit code 1). `vite.config.ts` had no `test.include`
scoping, so vitest's default file-discovery glob matched
`e2e/*.spec.ts` (Playwright specs using Playwright's own `test()` API,
incompatible with vitest's runner) and errored on all 3 files. Since this
matrix change is what would newly make CI *actually exercise* that already-
broken step for the first time (no commit had ever existed to trigger CI
before this session), shipping the coverage fix without addressing it would
have produced a guaranteed-red job. Scoped as the smallest fix that doesn't
expand into finding #8's territory (writing real unit tests): added
`test.include: ["src/**/*.{test,spec}.{ts,tsx}"]` (scoped to where real
tests will live, excluding `e2e/`) and `test.passWithNoTests: true` (exit 0
when legitimately zero unit tests exist yet, rather than treating that as a
failure). Also had to switch `vite.config.ts`'s `defineConfig` import from
`"vite"` to `"vitest/config"` — vitest's re-export is what actually types
the `test` key; plain `vite`'s `defineConfig` doesn't know about it and
failed `tsc -b` with `error TS2769: ... 'test' does not exist`.

- Files changed: `.github/workflows/ci.yml`, `apps/web/vite.config.ts`
- Tests added: none (CI/tooling-config change, not application logic) —
  verified by running every matrix-job step locally for all 4 apps:
  - `npm run build` (install already covered by earlier work in this
    session): exit 0 for `web`, `student-portal`, `trainer-portal`,
    `corporate-portal`.
  - `npm run test --if-present`: exit 0 for all 4 (`web` now reports
    "No test files found, exiting with code 0" instead of crashing;
    the other 3 skip silently since they have no `test` script).
  - Full backend regression suite unaffected (no Python changes):
    211/211 passing.
- Risks: none identified for existing behavior — `apps/web`'s production
  build output is unaffected (`vitest/config`'s `defineConfig` is a
  type-only-relevant re-export of vite's own; runtime `vite build` behavior
  is unchanged, confirmed by comparing build output before/after). The only
  behavior change is `npm run test` going from "crashes" to "correctly
  reports no tests" — strictly a bug fix, not a new capability.

## 4. Security

**Finding #1 (Critical):** see below.

**Finding #9 (Medium):** already covered in `docs/project-audit.md` — global rate limiting, not tuned per-endpoint. Account lockout (`modules/authentication/repository.py`) is a real compensating control already in place, which is why this is Medium and not High.

### Critical: default JWT secret has no production guard

- Evidence: `apps/api/app/core/config.py` line 52 — `JWT_SECRET_KEY: str = "change_me_in_production_min_32_chars"` — a string that is publicly visible to anyone who has ever seen this source code. `apps/api/app/core/security.py` signs and verifies every access/refresh token with exactly this value if it's never overridden. `apps/api/app/core/config.py`'s `is_production` property and `main.py`'s only two uses of it (lines 51-52, gating `/api/docs`/`/api/redoc`) confirm there is **no equivalent gate on `JWT_SECRET_KEY`** — the app boots and serves traffic normally even in `ENVIRONMENT=production` with the default secret still active.
- Impact: if an operator sets `ENVIRONMENT=production` (required for HSTS, disabling `/api/docs`, etc. — see `docs/deployment/production-checklist.md`) but misses `JWT_SECRET_KEY` — one line among ~30 in `.env` — anyone can forge a JWT for **any user, including a superuser**, using a secret already sitting in the source tree. This is a complete authentication bypass, not a hardening gap. It requires only a plausible, easy human mistake to trigger, not a sophisticated attack.
- Fix: fail fast at startup (Pydantic validator on `Settings`, or an explicit check early in `create_app()`) — if `is_production` is true and `JWT_SECRET_KEY` equals the known default (or is under some minimum length/entropy), raise and refuse to start rather than silently serving traffic.
- Effort: Small (1 hour) — a validator + one test asserting the app fails to construct `Settings`/boot under that condition.

**This is the Critical issue I'll fix in this turn**, per your instruction to auto-fix Critical findings.

## 5. Performance

**Finding #13 (Low):** already flagged in `docs/deployment/production-checklist.md` (report aggregations fetching up to 10,000 rows and aggregating in Python). No new performance findings from this pass — connection pool sizing (`DB_POOL_SIZE=20`/`DB_MAX_OVERFLOW=10` in `apps/api/app/db/session.py`) is reasonable for the documented single-replica default and is already flagged there as something to multiply by replica count. GZip compression, response envelope consistency, and index coverage on migration foreign keys were all previously verified real.

## 6. Monitoring

**Finding #10 (Medium):** Prometheus scrape config, Grafana dashboards, and alert rules (`infrastructure/monitoring/`) are real and were verified in the prior audit. What's genuinely missing: no distributed tracing or APM (no `opentelemetry`, `sentry_sdk`, or similar in `apps/api/requirements.txt`, confirmed by direct search).

- Impact: metrics answer "is something wrong" (latency/error-rate graphs), but not "which specific request/database call caused it" — an operator debugging a slow endpoint has structured logs (with request-ID correlation, which is genuinely good) but no automatic span/trace linking a slow HTTP request to the specific slow DB query or external call inside it.
- Fix: not a quick fix — requires picking a backend (Sentry for error aggregation is the smaller lift; OpenTelemetry + Jaeger/Tempo for full tracing is larger) and instrumenting. Recommend Sentry first (smallest effort/value ratio) as a separate follow-up, not part of this pass.
- Effort: Medium (Sentry: ~1 day integration + testing) to Large (OpenTelemetry: multi-day, touches every service boundary).

## 7. Logging

**Finding #6 (High):** Structured logging (`apps/api/app/core/logging_config.py`) with request-ID correlation is real and already verified. What's missing: nothing ships those logs anywhere durable. `infrastructure/` has no Loki, Fluentd, Fluent Bit, or CloudWatch agent configuration of any kind (confirmed by direct search — zero matches).

- Impact: in Kubernetes, container stdout is ephemeral — once a pod is evicted, rescheduled, or simply rotates past the node's log retention, those logs are gone. For a system that will eventually handle payroll and financial audit trails, being unable to retrieve request-level logs from more than a few hours/days ago (whatever the node's local log rotation allows) is a real operational gap, independent of the `AuditLog` database table (which captures data *changes*, not request/error logs).
- Fix: this is inherently deployment-specific (which log aggregation backend a given deployment already has access to), so a single fix isn't universal — but a minimum viable version (a Fluent Bit DaemonSet shipping to whatever's configured, with a documented example for CloudWatch Logs since Terraform already targets AWS) would close the gap for the primary deployment path this codebase already assumes.
- Effort: Medium (half a day for a Fluent Bit DaemonSet + CloudWatch Logs example config, following the same pattern as `infrastructure/monitoring/`).

## 8. Testing

**Finding #8 (Medium):** already documented in `docs/project-audit.md`. Backend testing (205 tests across unit/api/integration/security, verified passing) is genuinely strong. `tests/performance/locustfile.py` provides real load-test coverage. The gap is specifically frontend unit tests.

## 9. Scalability

**Finding #11 (Low):** `infrastructure/terraform/database.tf` provisions a single RDS instance (with Multi-AZ failover, not read scaling) and one ElastiCache replication group. There's no read replica, so all reads (which for an ERP with heavy reporting/dashboard usage are a meaningful share of traffic) hit the same instance as writes.

- Impact: at current scale (verified: this is a new platform, not yet carrying production traffic) this is not an active problem — it's scaling headroom, not a bug. Flagged as Low specifically because fixing it now, before real traffic/query patterns exist to size it against, would be premature.
- Fix: add an `aws_db_instance` read replica + route read-heavy report/dashboard queries to it, once real read/write ratios are known.
- Effort: Medium, but explicitly **not recommended until there's production traffic data to justify it** — this is the one finding in this audit I'd recommend deferring rather than scheduling.

## 10. Disaster Recovery

RDS-level DR (`infrastructure/terraform/database.tf`) is genuinely solid: 14-day automated backup retention, a defined backup window, deletion protection gated correctly on `environment == "production"`, and Multi-AZ failover available via the `enable_multi_az` toggle. This is real, verified infrastructure, not a gap.

The gap is entirely at the application layer — see Backup & Restore below — and in documentation: no runbook exists describing an actual DR procedure (which snapshot to restore, how to point the app at a restored instance, expected RTO/RPO). This isn't separately scored since it's really the documentation half of finding #2/#3.

## 11. Backup & Restore

**Finding #2 (High):** `modules/backups/service.py` and `modules/backups/routes.py` implement trigger + list + download-URL for a `pg_dump`-based backup, uploaded to MinIO/S3. There is no restore endpoint, service method, or CLI script anywhere in the codebase (confirmed: no `restore` match anywhere in `modules/backups/`).

- Impact: for a deployment relying on this feature as its primary backup mechanism (i.e., not using RDS-managed backups — the self-hosted/docker-compose path this codebase also supports), there is a real dump file sitting in object storage, but genuinely no tested, documented, or automated way to get it back into a database. An operator would have to manually download the file and run `pg_restore`/`psql` by hand, with no guidance in the codebase for how.
- Fix: at minimum, document the manual restore procedure (which this audit can write without touching application code); ideally, add a `POST /backups/{id}/restore` admin-only endpoint or a documented CLI script, gated behind explicit confirmation given how destructive a restore is.
- Effort: Documentation-only fix: Small (an hour). A real restore endpoint: Medium-Large, and — given how destructive a mistaken restore would be — deserves its own careful design pass rather than being rushed through an automated "fix Critical issues" loop. **Recommend documenting the manual procedure now, and treating a self-service restore endpoint as separate follow-up work**, not part of this session's fix pass.

**Finding #3 (High):** No automated schedule triggers `modules/backups`. `apps/api/app/core/celery_app.py`'s `beat_schedule` covers overdue-invoice detection and scheduled reports (confirmed present) but has no backup entry — confirmed by direct search.

- Impact: for a deployment using this module as its DR mechanism, a backup only exists if a human remembers to click "Trigger Backup" in the admin UI. There is no floor of "at least a daily backup always exists."
- Fix: add `celery_app.conf.beat_schedule["backups-daily-trigger"]` calling a new task that runs `BackupService.trigger_backup()` for a system account, following the exact pattern already used for `accounting.mark_overdue_invoices` and `reports.run_due_scheduled_reports`.
- Effort: Small (1-2 hours) — one new task function + one beat schedule entry, following an existing pattern exactly.

**Finding #12 (Low):** No retention/cleanup policy — once automated backups exist (finding #3), nothing ever deletes old ones, so storage cost grows unbounded over time. Low severity because it's a cost/hygiene issue, not a DR risk, and only becomes relevant once #3 is fixed.

## 12. Operational Readiness

**Finding #7 (Medium):** No documented rollback procedure exists anywhere in `docs/` or `infrastructure/` (confirmed: zero matches for "rollback" in either directory). `docs/deployment/production-checklist.md` covers pre-deploy steps thoroughly but stops short of "what do you do if the deploy is bad."

- Impact: in an incident, the first response is usually "roll back" — without a documented procedure (is it `kubectl rollout undo`? Does the Alembic migration need a corresponding manual downgrade? Is the previous image tag retained?), an on-call engineer is improvising during an active incident.
- Fix: add a "Rollback" section to `docs/deployment/production-checklist.md` covering: `kubectl rollout undo deployment/erpx-api -n erpx` (K8s handles the app-code rollback since `image: ghcr.io/gir-technologies/erpx-api:latest` — recommend pinning to immutable tags/digests rather than `:latest` for this to be reliable, a related sub-finding), and the separate question of whether the bad deploy included a forward-only Alembic migration (in which case code rollback alone isn't sufficient — this needs explicit guidance since migrations here are reversible, per the prior audit, but running `alembic downgrade` in production is its own risk that needs a documented decision tree, not just "it's technically possible").
- Effort: Small (documentation only, 1-2 hours) for the rollback runbook. The `:latest` tag → immutable tag/digest change is a separate, very small infra fix (`infrastructure/kubernetes/api-deployment.yaml` / `web-deployment.yaml` / `celery-deployment.yaml`, and `.github/workflows/docker-publish.yml`'s tagging strategy).

---

## Fix plan

Per your instructions, only **Critical** findings are auto-fixed in this pass. There is exactly one: **Finding #1**, the missing production guard on the default JWT secret.

**Status: fixed.** `apps/api/app/core/config.py`'s `Settings` gained a
`model_validator(mode="after")` that raises (refusing to construct
`Settings`, and therefore refusing to import `app.main` / boot the
application at all) if `ENVIRONMENT` is production and `JWT_SECRET_KEY`
either contains `change_me` (case-insensitive — catches both known
placeholder spellings already in this codebase, the Python field default
*and* `.env`'s own scaffold value, which are different strings) or is under
32 characters. Verified two ways: `tests/unit/test_config.py` (6 new tests,
all passing) and a direct manual check —
`ENVIRONMENT=production python -c "from app.core.config import Settings; Settings()"`
against the actual current `.env` correctly raises
`ValidationError: JWT_SECRET_KEY is still a placeholder value...` rather
than booting. Full regression suite: 211/211 passing (205 before this fix +
6 new), 0 regressions. Development-mode boot confirmed unaffected (the
guard only activates when `ENVIRONMENT=production`).

The High-severity findings (#2, #3, #4, #5, #6) are real and worth doing soon, but per your own scoping ("do not add new business features," "do not redesign existing modules") and given several of them (#2 especially) involve genuinely risky/destructive capability (a restore endpoint) that deserves deliberate design rather than being rushed through an automated loop — I'm listing them here with effort estimates and stopping short of auto-implementing anything beyond the one Critical fix, so you can direct which of these to tackle next and in what order.
