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
| 2 | Backup & Restore | No backup restore capability anywhere in the application layer | High — **fixed** |
| 3 | Backup & Restore | Application-level backups (`modules/backups`) are manual-only — no scheduled/automated trigger | High — **fixed** |
| 4 | Docker | Single-stage build ships build tooling into the runtime image; container runs as root | High — **fixed** |
| 5 | CI/CD | 3 of 4 frontend apps have no test script and are not built/tested in CI at all | High — **fixed** |
| 6 | Logging | No log shipping configured — container stdout is the only sink; logs are lost on pod eviction/restart | High — **fixed** |
| 7 | Operational Readiness | No documented rollback procedure for a bad deployment | Medium — **fixed** |
| 8 | Testing | `apps/web`'s `npm run test` (vitest) has zero test files behind it (already noted in `docs/project-audit.md`, included here for completeness) | Medium |
| 9 | Security | Global rate limiting only — auth endpoints share the same 100/min budget as read-only list endpoints (mitigated by account lockout) | Medium — **fixed (2026-07-29)** |
| 10 | Monitoring | Prometheus + Grafana + alert rules exist, but no distributed tracing / APM / error aggregation (Sentry, OpenTelemetry) | Medium — **error aggregation (Sentry) fixed (2026-07-29); full OpenTelemetry tracing still deferred** |
| 11 | Scalability | No database read replica; all reads and writes hit the single RDS primary | Low |
| 12 | Backup & Restore | No retention/cleanup policy for application-level backup files in MinIO/S3 | Low |
| 13 | Performance | Some report aggregations fetch up to 10,000 rows and aggregate in Python rather than `GROUP BY` (already noted in `docs/deployment/production-checklist.md`) | Low |
| 14 | Accessibility | No accessibility (WCAG 2.1 AA) tooling existed in any of the 4 frontend apps; near-zero ARIA/alt attribute usage found across all of them | Medium — **Phase 1 (tooling) + Phase 2 (shared `CardTitle` fix, -4 violations) fixed; 20 of 24 original violations remain, Phase 3+ not started** |
| 15 | Security | No dependency vulnerability scanning existed anywhere in CI; scanning added and immediately surfaced real Critical/High vulnerabilities already present in both the backend and all 4 frontend apps | Medium — **scanning tooling fixed; `python-multipart` HIGH×4 fixed and fully regression-tested (2026-07-29); frontend `vitest` CRITICAL fixed via `2.1.9→3.2.6` upgrade (2026-07-29, +2 Moderate cleared, 0 new); `python-jose` CRITICAL investigated and deliberately deferred (transitive `pyasn1` trade-off); `starlette`/`ecdsa` (backend) still open; frontend HIGH×11 (`eslint`/`vite` toolchain) + 3 Moderate still open** |

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

**Status: fixed (2026-07-29).** Confirmed via direct evidence before changing
anything: `apps/api/app/main.py` applied exactly one `Limiter` with a single
`default_limits=[settings.RATE_LIMIT_DEFAULT]` (`"100/minute"`), and a repo-wide
search for `@limiter.limit`/`limiter.limit` found zero per-route decorators
anywhere — every endpoint, including `/auth/login`, genuinely shared the same
100/minute budget as read-only list endpoints, exactly as the finding states.

**Root cause of why no per-route limit existed:** the `Limiter` instance was
defined inline in `app/main.py`, which every module's `routes.py` is imported
by (via `app/api/v1/router.py`) — so a route module trying `from app.main
import limiter` would hit a circular import. Fixed by extracting the
`Limiter` into its own dependency-free module, `apps/api/app/core/limiter.py`;
`app/main.py` now imports it from there instead of constructing it inline
(identical `Limiter(key_func=get_remote_address,
default_limits=[settings.RATE_LIMIT_DEFAULT])` call, just relocated), and
`modules/authentication/routes.py` imports the same singleton to apply
per-route decorators.

**Endpoints tightened** — the six pre-authentication endpoints in
`modules/authentication/routes.py` reachable by an anonymous attacker with no
credential at all (the actual threat model rate limiting defends against —
credential stuffing, account-creation spam, password-reset-token guessing,
verification-email spam):

| Endpoint | New limit | Reasoning |
|---|---|---|
| `POST /auth/register` | 10/minute | Slows mass account-creation/spam |
| `POST /auth/login` | 10/minute | Slows credential-stuffing/brute force per IP; account lockout remains the deeper per-account defense |
| `POST /auth/refresh` | 20/minute | Looser than login/register since legitimate SPA sessions call this automatically and somewhat frequently, but still 5x tighter than the global default |
| `POST /auth/forgot-password` | 5/minute | Slows password-reset-token guessing and email-bombing a victim's inbox |
| `POST /auth/reset-password` | 5/minute | Same reasoning as forgot-password |
| `POST /auth/resend-verification` | 5/minute | Slows verification-email spam |

**Deliberately left untouched:** `/auth/logout`, `/me`, `/change-password`,
`/2fa/setup`, `/2fa/confirm`, `/2fa/disable` — all require an already-valid
`Authorization` bearer token (`get_current_active_user`), so they aren't
reachable by an anonymous attacker in the first place; tightening them was
judged out of scope for this finding, which is specifically about the
pre-auth attack surface. The global 100/minute default still applies to
every other endpoint in the application, unchanged.

**A real regression this change surfaced and fixed, not swept under the
rug:** the shared `Limiter`'s in-memory hit counters are a process-wide
singleton, and the backend test suite imports the real `app` object exactly
once for the whole pytest session (`tests/_fixtures.py`) — so the first attempt
at this fix (limits applied with no test-side accommodation) caused 24
unrelated test failures across `tests/api/test_auth.py`, `test_two_factor.py`,
`test_hackathons.py`, `test_placements.py`, `test_trainer_self_service.py`,
`test_lms_transcripts.py`, and `test_workshops.py` — all of them use
`/auth/register`/`/auth/login` as ordinary HTTP setup machinery (27 and 28
real calls respectively, scattered across the whole suite), and the shared
limiter's hit count accumulated across every earlier test file in the same
pytest session until a later, entirely unrelated test's legitimate call
tripped the same budget. Root-caused via the real 429 responses in the
failure log (`assert 429 == 201`), not assumed. Fixed at the correct layer:
`tests/_fixtures.py`'s shared `client` fixture (used by `tests/api`,
`tests/integration`, and `tests/security`) now calls `limiter.reset()` before
every test, so each test starts with a clean rate-limit slate — this does
not touch the production limit values at all, it only isolates test-to-test
state, exactly the same isolation `db_session`/`db_session`'s transaction
rollback already provides for the database.

**Files changed:** `apps/api/app/core/limiter.py` (new),
`apps/api/app/main.py`, `modules/authentication/routes.py`,
`tests/_fixtures.py`, `tests/api/test_auth_rate_limiting.py` (new).

**Validation performed:** new `tests/api/test_auth_rate_limiting.py` (5
tests, all passing) — proves each limited endpoint actually returns 429 past
its threshold, proves limits are scoped per-route (exhausting `/login`'s
budget doesn't affect `/forgot-password`'s), and proves an endpoint that
was never given a per-route limit (`/me`) is unaffected. Full backend
regression suite re-run end-to-end: **262/262 passing** (257 pre-existing +
5 new), 0 regressions. No backend lint/typecheck/build CI step exists in
this project (verified, not assumed, in the prior `python-multipart`
finding's validation) — the closest equivalent, a clean full-suite
collection and run with zero import errors, already covers this change.

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

**Status: error aggregation (Sentry) fixed (2026-07-29).** The smaller,
higher-value half of this finding — error/exception aggregation — is now
implemented. Full distributed tracing / APM (OpenTelemetry + Jaeger/Tempo)
remains deliberately out of scope (larger, multi-day, touches every service
boundary); Sentry performance tracing is wired but disabled by default
(`SENTRY_TRACES_SAMPLE_RATE=0.0`) and can be enabled later without code
changes.

### Sentry integration (finding #10 — error aggregation)

**Root cause:** the platform had Prometheus metrics (aggregate "is
something wrong") and structured request-ID-correlated logs, but no
error-aggregation service — an operator had no single place where
unhandled exceptions across the API and Celery workers are collected,
deduplicated, alerted on, and tied back to a request. The catch-all
`Exception` handler's own message even promised "our team has been
notified," which wasn't literally true.

**Integration point & design:**
- `apps/api/app/core/observability.py` (new) — a single `init_sentry(service_name)`
  shared by both entrypoints, mirroring the existing shared
  `configure_logging()` pattern. Called from `app/main.py` (before
  `create_app()`, so the FastAPI/Starlette integration wraps the app) as
  `erpx-api`, and from `app/core/celery_app.py` as `erpx-celery`.
- **Capture targets, all three covered:** FastAPI/Starlette request
  exceptions and process-level unhandled exceptions (Sentry's auto-enabled
  integrations), plus Celery background-task failures (auto-enabled Celery
  integration, since celery is imported in that entrypoint). The catch-all
  `@app.exception_handler(Exception)` in `app/core/exception_handlers.py`
  now *also* calls `sentry_sdk.capture_exception(exc)` explicitly — because
  that handler returns a JSON envelope, Starlette treats the 500 as
  "handled," so it never reaches the server-error layer the framework
  integration hooks; without the explicit call these app-level 500s would
  go uncaptured. Sentry's default `DedupeIntegration` prevents any double
  reporting. The capture is tagged with the request's `request_id` for
  log↔error cross-referencing.
- **Local vs production behavior:** entirely env-driven. `SENTRY_DSN` is
  empty by default → Sentry is fully disabled (no init, no network calls, a
  pure no-op) — the intended local-dev behavior. It activates only when a
  real DSN is set (staging/production). `SENTRY_ENVIRONMENT` falls back to
  `ENVIRONMENT` when blank.
- **PII / credential filtering:** `send_default_pii=False` is forced, so
  Sentry never attaches request bodies, cookies, the `Authorization`
  header, or client IP. A `before_send` hook additionally drops cookies and
  redacts `authorization`/`cookie`/`x-api-key`/`x-csrf-token` headers to
  `[Filtered]`, layered on top of Sentry's built-in `EventScrubber`
  (which redacts values for keys like `password`/`secret`/`token`/`api_key`).

**Environment variables** (documented in `.env.example`):
`SENTRY_DSN` (blank = disabled), `SENTRY_ENVIRONMENT` (blank = falls back to
`ENVIRONMENT`), `SENTRY_RELEASE` (blank = none), `SENTRY_TRACES_SAMPLE_RATE`
(default `0.0` = error reporting only, no perf tracing).

**Dependency:** `sentry-sdk==2.66.1` added to `apps/api/requirements.txt`.
Verified conflict-free against the pinned stack — its only runtime deps
(`urllib3>=1.26.11`, `certifi`) were already satisfied; a real
`pip install --dry-run` changed nothing else.

**Validation:** new `tests/unit/test_observability.py` (4 tests — disabled
no-op path, initialized path with PII off + env fallback, header/cookie
scrubbing, and tolerance of non-HTTP events) all pass. Verified both
entrypoints (`app.main`, `app.core.celery_app`) import and boot cleanly
with Sentry disabled. End-to-end verified that a route raising an exception
drives the registered handler to call `sentry_sdk.capture_exception` with
the real exception object. `sentry_sdk.capture_exception` confirmed to be a
safe no-op when uninitialized. Full backend regression suite re-run:
**266/266 passing** (262 pre-existing + 4 new), 0 regressions.

## 7. Logging

**Finding #6 (High):** Structured logging (`apps/api/app/core/logging_config.py`) with request-ID correlation is real and already verified. What's missing: nothing ships those logs anywhere durable. `infrastructure/` has no Loki, Fluentd, Fluent Bit, or CloudWatch agent configuration of any kind (confirmed by direct search — zero matches).

- Impact: in Kubernetes, container stdout is ephemeral — once a pod is evicted, rescheduled, or simply rotates past the node's log retention, those logs are gone. For a system that will eventually handle payroll and financial audit trails, being unable to retrieve request-level logs from more than a few hours/days ago (whatever the node's local log rotation allows) is a real operational gap, independent of the `AuditLog` database table (which captures data *changes*, not request/error logs).
- Fix: this is inherently deployment-specific (which log aggregation backend a given deployment already has access to), so a single fix isn't universal — but a minimum viable version (a Fluent Bit DaemonSet shipping to whatever's configured, with a documented example for CloudWatch Logs since Terraform already targets AWS) would close the gap for the primary deployment path this codebase already assumes.
- Effort: Medium (half a day for a Fluent Bit DaemonSet + CloudWatch Logs example config, following the same pattern as `infrastructure/monitoring/`).

**Status: fixed.** Fluent Bit + Grafana Loki (see
`docs/logging-architecture-proposal.md`) is implemented — Kubernetes
manifests (`infrastructure/kubernetes/{loki-deployment,fluent-bit-daemonset,loki-bucket-init-job}.yaml`),
Docker Compose services (`docker-compose.yml` + `docker-compose.monitoring.yml`),
Grafana datasource + "ERPX Logs Overview" dashboard, and Prometheus
scrape targets/alerts for the pipeline's own health
(`infrastructure/monitoring/{prometheus.yml,alert_rules.yml}`). Full
implementation detail and validation evidence: proposal Section 7.
Operational runbook: `docs/operations/logging-runbook.md`.

The proposal's own Risk Assessment (Section 5) flagged two High-severity
risks that had to be closed *before* shipping could safely begin; those
prerequisites were implemented and tested first, in a separate prior
change (full detail in the proposal's Section 6):

1. **Structured JSON logging standardized on every entrypoint, including
   Celery.** `apps/api/app/core/celery_app.py` previously never called
   `configure_logging()` — the real `celery -A app.core.celery_app worker/
   beat` entrypoints import only that module, never `app/main.py`, so
   Celery processes silently logged plain, un-configured `key=value` text
   with no JSON and no schema fields at all, despite calling the identical
   `get_logger()` API every task module uses. This was a real,
   previously-undocumented bug, found and fixed as part of this work.
   `apps/api/app/core/logging_config.py` now emits a fixed, unified schema
   in production (`timestamp`, `level`, `message`, `service`,
   `environment`, `request_id`, `organization_id`, `user_id`, `module`,
   `logger`, `hostname`, `pod_container_metadata`, `exception_details`)
   from both the API and Celery entrypoints identically.
2. **`organization_id` correlation.** `apps/api/app/core/audit_context.py`'s
   existing setters now also bind into `structlog.contextvars`, reusing the
   same two call sites that already populate `AuditLog` rows — no new
   resolution mechanism. Closes the specific gap the proposal's Section 5
   called out: without this, an operator with log access could query
   across every organization with no built-in scoping, on a platform
   that's otherwise organization-scoped everywhere else.

Also completed as part of "ingress apps" standardization:
`infrastructure/nginx/nginx.conf` (Compose path) gained a JSON
`log_format` correlating `request_id` via the API's own `X-Request-ID`
response header — previously nginx ran on compiled defaults with zero
`log_format`/`access_log` directives.

Tested: new `tests/unit/test_logging_config.py` (11 tests, all passing),
including a subprocess-based regression test reproducing the exact Celery
entrypoint import path to guard against the bug above recurring silently.
Full regression suite re-run: 223/223 passing (212 before this change + 11
new), 0 regressions.

Loki + Fluent Bit shipping itself: implemented and validated against a
real Fluent Bit + Loki pair on this project's actual standalone MinIO
(bucket creation, ingestion, correct label extraction, 0 pipeline errors
— see proposal Section 7 for the full evidence). One gap disclosed rather
than hidden: the LogQL query-read path returned empty results in that
same short-lived validation instance despite the ingester provably
holding the data — reproduced identically with plain filesystem storage,
ruling out the MinIO integration as the cause, but not conclusively
root-caused. Tracked as a pre-production validation gate in
`docs/deployment/production-checklist.md` and a troubleshooting entry in
`docs/operations/logging-runbook.md`. No application code changed in this
phase — infrastructure/config/docs only; full regression suite re-run
regardless, 0 regressions (see proposal Section 7).

## 8. Testing

**Finding #8 (Medium):** already documented in `docs/project-audit.md`. Backend testing (257 tests across unit/api/integration/security, verified passing) is genuinely strong. `tests/performance/locustfile.py` provides real load-test coverage. The gap is specifically frontend unit tests.

**Status: Auth client unit test infrastructure completed across all four
frontend applications (2026-07-28).**

**Status: partially fixed (2026-07-28), first increment.** `apps/web` had a
`vitest` test runner configured (`vite.config.ts`) but zero actual unit
test files — confirmed during the Complete Enterprise Software Engineering
Audit. Rather than attempt "add frontend test coverage" as one
undifferentiated task across 4 apps and ~118 routes, the highest-leverage,
narrowly-scoped first increment was chosen: real unit tests for
`apps/web/src/api/client.ts`'s auth-header-attachment and
401→refresh→retry interceptor logic — the single piece of frontend code
every authenticated request in the app depends on, previously completely
untested.

New file `apps/web/src/api/client.test.ts` (8 tests, all passing): request
interceptor attaches/omits the `Authorization` header correctly; non-401
errors pass through without attempting a refresh; a 401 with no refresh
token logs out without calling the refresh endpoint; a 401 with a valid
refresh token refreshes, updates the store, and retries the original
request with the new token; a failed refresh call logs out; a request
that already retried once does not trigger a second refresh (no infinite
loop); and — the most valuable case — 3 concurrent 401s while a refresh is
already in flight are queued behind exactly **one** refresh call, not
three, and all three original requests still resolve correctly once it
completes.

Added `axios-mock-adapter` as a new devDependency (`apps/web/package.json`)
— attaches to the real `apiClient`/`axios` instances at the HTTP-adapter
layer, so the interceptors and the real Zustand auth store both run
unmocked; only the network boundary is faked. This is a test-only utility,
not a new architectural choice — axios itself was already the chosen HTTP
client.

Real gotcha found and fixed during implementation, not swept under the
rug: `client.ts`'s refresh call deliberately goes through the bare
`axios` import rather than `apiClient` (so a request already marked
`_retry` can't recursively re-enter `apiClient`'s own interceptors) — the
test file mocks both instances separately for exactly that reason, rather
than assuming one mock covers both request paths.

`apps/web`'s existing `vite.config.ts` already scoped `test.include` to
`src/**/*.{test,spec}.{ts,tsx}` specifically to exclude Playwright's
`e2e/*.spec.ts` specs from vitest's runner — no config change was needed.

**Explicitly not done in this increment** (tracked as separate follow-up
work, not silently deferred): unit test infrastructure for
`student-portal`/`trainer-portal`/`corporate-portal` (currently zero test
runner configured in any of the three); broader `apps/web` component/page
coverage beyond this one file; accessibility tooling (a distinct, still-open
finding from the RC1 audit).

**Status: second increment (2026-07-28).** `apps/student-portal/src/api/client.ts`
and `auth-store.ts` were confirmed byte-identical to `apps/web`'s
already-tested versions — but `student-portal` is a separately built and
deployed app (own `package.json`, own Vite bundle, own CI matrix entry in
`.github/workflows/ci.yml`), so having `apps/web`'s tests pass proves
nothing about whether `student-portal`'s own build actually exercises the
same code correctly. Added the same vitest setup (`vite.config.ts`'s
`defineConfig` import switched to `vitest/config`, matching the exact fix
already applied to `apps/web`'s config; `vitest` + `axios-mock-adapter`
devDependencies; `"test": "vitest run"` script) and ported the identical,
already-proven 8-test suite. All 8 pass identically. No production code
in `student-portal` was changed — `client.ts`/`auth-store.ts` were only
read to confirm the byte-for-byte match, not edited.

`trainer-portal` and `corporate-portal` remain untouched — same gap,
tracked as continued follow-up, not yet started.

**Status: third increment (2026-07-28).** `apps/trainer-portal/src/api/client.ts`
and `auth-store.ts` confirmed byte-identical to `apps/web`'s and
`apps/student-portal`'s (direct `diff`, zero differences) — same reasoning
as the second increment applies: identical source code, but a third
independently built/deployed app, so it needs its own real test run.
Applied the identical pattern: `vite.config.ts`'s `defineConfig` import
switched to `vitest/config` (trainer-portal's own dev-server port, 5175,
preserved unchanged); `vitest` + `axios-mock-adapter` devDependencies;
`"test": "vitest run"` script (picked up automatically by the existing CI
matrix job, no workflow change needed); the identical, already-proven
8-test suite ported verbatim. All 8 pass. No production code in
`trainer-portal` was changed.

`corporate-portal` remains untouched — same gap, one app left, tracked as
continued follow-up.

**Status: fourth and final increment (2026-07-28) — the auth-client
portion of this finding is now closed.** `apps/corporate-portal/src/api/client.ts`
and `auth-store.ts` confirmed byte-identical to the other three apps'
(direct `diff`, zero differences). Applied the identical pattern:
`vite.config.ts`'s `defineConfig` import switched to `vitest/config`
(corporate-portal's own dev-server port, 5176, preserved unchanged);
`vitest` + `axios-mock-adapter` devDependencies; `"test": "vitest run"`
script; the identical, already-proven 8-test suite ported verbatim. All 8
pass. No production code in `corporate-portal` was changed, and
`apps/web`/`apps/student-portal`/`apps/trainer-portal` were not touched in
any of the four increments.

**Summary across all four increments:** every one of ERPX's 4 frontend
applications (`apps/web`, `apps/student-portal`, `apps/trainer-portal`,
`apps/corporate-portal`) now has vitest configured, a working `npm run
test` script wired into the existing CI matrix job with no workflow
changes required, and a real, passing 8-test suite covering the exact
piece of code every authenticated request in every app depends on
(`src/api/client.ts`'s token-attachment and 401-refresh-retry
interceptors) — 32 frontend unit tests total, all passing, all exercising
real production code against a mocked HTTP boundary only.

**What "frontend unit test coverage" still means beyond this** — this
increment deliberately covered one file per app, chosen because it was
the single highest-risk, completely untested piece of logic. It is not
the same as comprehensive frontend coverage. Still genuinely untested,
tracked as separate future work, not silently rolled into this finding's
"done" status:
- **Forms**: react-hook-form + Zod validation logic across ~40 business
  feature forms (crm/leads, accounting/invoices, hr/payroll, etc.) — zero
  tests.
- **Pages**: the ~118 route components in `apps/web` alone (plus each
  portal app's own pages) — zero component/rendering tests.
- **Hooks**: custom React Query hooks per feature (`useLeads`,
  `useInvoices`, etc.) — zero tests; no `@testing-library/react` or
  `@testing-library/react-hooks`-equivalent is installed in any of the 4
  apps yet, which would be needed for this.
- **Tables**: the shared `components/ui/table.tsx` primitives and their
  per-page usage (sorting, filtering, pagination where implemented ad hoc
  per page) — zero tests.
- **State management**: the Zustand auth store's own reducers are
  exercised indirectly (via the client tests, which call `setState`/read
  `getState`) but have no dedicated unit tests of their own; React Query
  cache/invalidation behavior is entirely untested.
- **Accessibility**: still a distinct, separately-tracked open item (near-zero
  ARIA/alt coverage, no `eslint-plugin-jsx-a11y`/`axe-core` in any app) —
  not a testing-infrastructure gap, a design/implementation gap; adding
  tests wouldn't close it on its own.
- **Visual/integration**: no component-level integration tests (e.g. "fill
  this form, submit, see this result") exist in any app — only the 3
  Playwright e2e specs in `apps/web` cover that class of behavior, and only
  for 3 flows (auth, leads, nav smoke).

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

**Status: fixed (2026-07-28)** — see "Implementation status" at the end of
this section for what was built. The design proposal below is kept
as originally written (it's what was actually implemented, not a
retrospective rewrite).

### Design proposal: `modules/backups` restore capability

#### Problem

`modules/backups` can produce a full-database `pg_dump` and upload it to
object storage, but there is no way — via the API, a CLI script, or
documentation — to get that dump back into a database. If this module is
ever relied on as the actual DR mechanism (true for the self-hosted /
docker-compose deployment path, which has no RDS-managed backups behind
it), a real incident today would mean: a real dump file exists in MinIO/S3,
and the person on call has to reconstruct the restore procedure from first
principles, under pressure, for the first time, during the incident itself.

#### Current implementation

`modules/backups/service.py`'s `BackupService.trigger_backup()`:
1. Runs `pg_dump -h <host> -p <port> -U <user> -d <db> -f <tmp>.sql
   --no-owner --no-privileges` (plain SQL format, **not** `-Fc`/custom
   format — this matters: it means the eventual restore tool is `psql`,
   not `pg_restore`).
2. Uploads the resulting `.sql` file to object storage at
   `backups/{job_id}.sql`.
3. Records a `BackupJob` row (`modules/backups/models.py`) with status,
   size, and a `storage_key`.

`modules/backups/routes.py` exposes `trigger`, `list`, `get`, and
`download-url` — all gated by `backups.manage`/`backups.view`, which
`modules/authorization/service.py` deliberately excludes from the default
Staff role (Administrator/Super Admin only).

Critically: `BackupJob` is **not organization-scoped**
(`modules/backups/models.py`'s own docstring: "every organization's data
lives in the same shared Postgres database... a 'backup' is inherently a
whole-database operation"). A restore is therefore not a
"restore this one customer's data" operation — it's "roll back every
tenant on the platform to the backup's point in time, simultaneously."
There is no way to restore a single organization's data in isolation given
this schema (row-level multi-tenancy, not database-per-tenant).

#### Proposed architecture

Given the blast radius above, I'm proposing something deliberately more
conservative than a simple `POST /backups/{id}/restore` endpoint:

1. **No self-service, one-click restore via the running application at
   all.** The API process that would serve that request is itself backed
   by the same database being overwritten — restoring out from under your
   own live connection pool is a well-known way to corrupt in-flight
   transactions and hand back inconsistent errors to users mid-restore.
   Real restores should happen with the API stopped or in maintenance mode.

2. **A standalone CLI script**
   (`apps/api/scripts/restore_backup.py`, following the existing
   convention of `apps/api/scripts/seed.py` / `seed_e2e.py`), run manually
   by an operator, outside the running API process:
   - Takes a `BackupJob` id (or `storage_key`) and downloads the dump from
     object storage via the existing `StorageClient`.
   - Requires an explicit `--yes-i-understand-this-overwrites-all-tenant-data`
     flag (or equivalent interactive confirmation reading back the target
     database name) before proceeding — mirrors the destructive-action
     confirmation pattern already used in this codebase's frontend for
     other high-stakes actions.
   - Runs `psql -h ... -f <downloaded>.sql` (matching the plain-SQL dump
     format already produced) against a database connection string passed
     explicitly on the command line — never silently inferred from
     `settings.DATABASE_URL`, so an operator can't accidentally restore
     into production while believing they're pointed at a staging
     restore-drill database.
   - Logs a real `AuditLog`-equivalent record of the restore action
     (who, when, which backup, which target) — likely a new
     `RestoreAttempt` row on `BackupJob` or a dedicated table, so a restore
     is itself auditable after the fact, consistent with this codebase's
     existing "every mutation is audited" design (`modules/audit/hooks.py`).

3. **A read-only `GET /backups/{id}/restore-instructions` API endpoint**
   (safe, non-destructive, fine to auto-implement later without a design
   review) that returns the exact CLI invocation for that specific backup
   — closes the "no guidance" half of the gap without touching the
   dangerous half.

4. **Explicitly out of scope for this proposal:** a fully automated,
   in-app restore button. If a future requirement genuinely needs
   self-service restore (e.g., a customer-facing "restore my own data to
   yesterday" feature), that requires database-per-tenant or
   schema-per-tenant partitioning first — a much larger architectural
   change than this finding, and not something to bundle in here.

#### Risks

- **Primary risk: total data loss across every tenant** if the wrong backup
  is chosen, or a restore is run against the wrong target database. This is
  the entire reason this is a design proposal and not an auto-fix.
- **Partial restore inconsistency:** the plain-SQL dump has no `--clean`
  flag today, so replaying it against a database that already has data
  will emit constraint-violation errors rather than cleanly replacing
  existing rows. The restore script needs to either add `--clean` to
  future dumps (changes finding #3/#12's output format too — needs to be
  decided together) or explicitly document "restore only into an empty
  database," which itself needs a documented procedure for how an operator
  gets an empty-but-correctly-migrated database ready (run migrations,
  then restore — order matters, since the dump includes data for tables
  that must already exist via Alembic).
- **Downtime during restore:** correctly requires the API stopped (see
  Proposed architecture #1) — this is a real operational cost that needs
  to be reflected in any RTO figure written down for this DR path.

#### Rollback strategy

If a restore itself goes wrong (e.g., wrong backup selected, or the
`psql` replay fails partway through): the target database is now in a
partially-restored, likely inconsistent state. The only safe rollback is
**restoring again from a known-good backup** (ideally one taken
immediately before the failed restore attempt) — there is no
"undo" for a partial SQL replay short of that. This is why the CLI script
proposal above should, as a refinement worth deciding at implementation
time, optionally take its own `pg_dump` of the *current* (pre-restore)
state before proceeding, so a botched restore has an immediate way back.

#### Migration plan

No schema/data migration is required for the CLI-script version of this
proposal. If the audit-trail refinement (a `RestoreAttempt` table) is
approved as part of this, that's one small additive Alembic migration,
following the exact pattern of every other migration in
`apps/api/alembic/versions/`.

#### Estimated implementation effort

- CLI script + confirmation flag + basic logging: **Small-Medium** (half a
  day to a day, including manual restore-drill testing against the
  standalone Postgres environment).
- `RestoreAttempt` audit table + migration: **Small** (an hour or two,
  following existing patterns exactly).

### Implementation status (2026-07-28)

**Status: fixed.** Implemented exactly as proposed above — CLI-only,
manual, confirmation-gated, no web-based restore endpoint. Full procedure:
`docs/operations/disaster-recovery-runbook.md`.

- `apps/api/scripts/restore_backup.py` (new): resolves a backup from a
  `BackupJob` id, a raw storage key, or a local file; verifies size and
  SHA-256 (new `backup_jobs.sha256` column, computed at backup time —
  `modules/backups/service.py`) plus a pg_dump-format sanity check before
  ever touching a database; refuses if the target has other active
  connections (`pg_stat_activity`) or already has tables (unless
  `--yes-wipe-existing-schema`); requires typed confirmation of the exact
  target database name unless `--force`; takes its own pre-restore safety
  `pg_dump` of the target by default; runs `psql -v ON_ERROR_STOP=1` so a
  partial failure is detected immediately rather than continuing past
  errors silently; on failure, prints the exact rollback path (restore
  again from the safety backup). `--database-url` is always explicit,
  never inferred from `settings.DATABASE_URL`. Distinct exit codes per
  failure category (argument error, backup invalid, target unsafe,
  confirmation declined, safety backup failed, restore failed, internal
  error) — see the runbook's table.
- Every attempt is logged to a local JSON-lines audit file (the primary,
  always-written trail) and, best-effort, to a new `restore_attempts`
  table (`apps/api/alembic/versions/0037_*.py`) if the target already has
  it.
- `packages/storage/client.py` gained `download_file()` (the restore
  script needs bytes on local disk for `psql -f`, unlike every existing
  caller which only ever needed presigned URLs or server-side uploads).

Tested: `tests/unit/test_restore_backup.py` (21 tests — argument parsing,
URL redaction/parsing, checksum/format checks, the confirmation prompt,
no database needed) and `tests/integration/test_restore_backup_integration.py`
(13 tests — real Postgres, real `pg_dump`/`psql` subprocesses, real
wipe-and-restore, real confirmation-decline and SHA-256-mismatch paths).
Every integration test creates and drops its own throwaway database
(`erpx_restore_test_<uuid>`) — the shared `erpx_test` database the rest of
the suite depends on is never touched by these tests. `tests/api/test_backups.py`
extended with one assertion confirming the new `sha256` field is correct.
Full regression suite re-run: **257/257 passing** (223 before this change
+ 21 new unit + 13 new integration), 0 regressions.

**Explicitly not implemented** (matches the proposal exactly): any
API endpoint, any web UI, any self-service/automated restore trigger. The
read-only `GET /backups/{id}/restore-instructions` endpoint the proposal
mentioned as safe-to-add-later remains unimplemented — it's non-destructive
and could be picked up as separate, small follow-up work if useful, but
wasn't part of this scope.
- `GET /backups/{id}/restore-instructions` read-only endpoint: **Small**
  (an hour) — safe to implement without further approval once the CLI
  script's actual invocation shape is finalized, since it only returns
  text.
- **Not estimated / explicitly deferred:** true self-service in-app
  restore, which would require the tenancy-model change described above.

**Waiting for your decision before implementing any part of this.**

**Finding #3 (High):** No automated schedule triggers `modules/backups`. `apps/api/app/core/celery_app.py`'s `beat_schedule` covers overdue-invoice detection and scheduled reports (confirmed present) but has no backup entry — confirmed by direct search.

- Impact: for a deployment using this module as its DR mechanism, a backup only exists if a human remembers to click "Trigger Backup" in the admin UI. There is no floor of "at least a daily backup always exists."
- Fix: add `celery_app.conf.beat_schedule["backups-daily-trigger"]` calling a new task that runs `BackupService.trigger_backup()` for a system account, following the exact pattern already used for `accounting.mark_overdue_invoices` and `reports.run_due_scheduled_reports`.
- Effort: Small (1-2 hours) — one new task function + one beat schedule entry, following an existing pattern exactly.

**Status: fixed.** Added `modules/backups/tasks.py` (new file), mirroring
`modules/accounting/invoices/tasks.py`'s exact pattern — an async helper
using `get_db_context()` for a fresh session, wrapped in a sync
`@celery_app.task` via `asyncio.run()`. Simpler than the invoices task
since `BackupJob` isn't organization-scoped, so no per-organization loop is
needed. Calls `BackupService.trigger_backup(triggered_by_user_id=None)` —
used `None` rather than inventing a synthetic "system user" account, since
`triggered_by_user_id` was already a nullable FK
(`modules/backups/models.py`) for exactly this reason; widened the
service method's type hint from `uuid.UUID` to `uuid.UUID | None` to match,
since this is now genuinely the first caller to pass `None`. Registered a
new `celery_app.conf.beat_schedule["backups-trigger-daily"]` entry
(`crontab(hour=2, minute=0)`, distinct from the existing 00:30 and `*/30`
entries) and added `modules.backups` to `autodiscover_tasks`.

- Files changed: `modules/backups/tasks.py` (new), `apps/api/app/core/celery_app.py`, `modules/backups/service.py` (one-line type hint fix)
- Tests added: `tests/api/test_backups.py::test_scheduled_backup_with_no_triggering_user_succeeds` — calls `BackupService.trigger_backup(triggered_by_user_id=None)` directly (the code path the new Celery task exercises, which has no HTTP route since it's never user-initiated) and confirms it completes successfully with a real `pg_dump` and a null `triggered_by_user_id`, rather than only being exercised via the API route (which always supplies a real user id). Also directly verified task registration: `python -c "from app.core.celery_app import celery_app; import modules.backups.tasks; ..."` confirms `backups.trigger_daily_backup` is registered and the beat schedule entry exists.
- Full regression suite: 212/212 passing (211 before this fix + 1 new), 0 regressions.
- Risks: none identified. The task is a thin wrapper around the
  already-tested `trigger_backup()` method; the only new runtime behavior
  is *when* it's called (a schedule) and *what* it's called with
  (`None` instead of a real user id), both covered by the new test.
  2:00 AM UTC chosen to avoid overlapping the existing 00:30 overdue-invoice
  sweep; no other scheduled task runs at that time. Doesn't address
  finding #12 (retention/cleanup of old backup files) — noted as a
  separate, lower-severity, explicitly-deferred finding below.

**Finding #12 (Low):** No retention/cleanup policy — once automated backups exist (finding #3), nothing ever deletes old ones, so storage cost grows unbounded over time. Low severity because it's a cost/hygiene issue, not a DR risk, and only becomes relevant once #3 is fixed.

## 12. Operational Readiness

**Finding #7 (Medium):** No documented rollback procedure exists anywhere in `docs/` or `infrastructure/` (confirmed: zero matches for "rollback" in either directory). `docs/deployment/production-checklist.md` covers pre-deploy steps thoroughly but stops short of "what do you do if the deploy is bad."

- Impact: in an incident, the first response is usually "roll back" — without a documented procedure (is it `kubectl rollout undo`? Does the Alembic migration need a corresponding manual downgrade? Is the previous image tag retained?), an on-call engineer is improvising during an active incident.
- Fix: add a "Rollback" section to `docs/deployment/production-checklist.md` covering: `kubectl rollout undo deployment/erpx-api -n erpx` (K8s handles the app-code rollback since `image: ghcr.io/gir-technologies/erpx-api:latest` — recommend pinning to immutable tags/digests rather than `:latest` for this to be reliable, a related sub-finding), and the separate question of whether the bad deploy included a forward-only Alembic migration (in which case code rollback alone isn't sufficient — this needs explicit guidance since migrations here are reversible, per the prior audit, but running `alembic downgrade` in production is its own risk that needs a documented decision tree, not just "it's technically possible").
- Effort: Small (documentation only, 1-2 hours) for the rollback runbook. The `:latest` tag → immutable tag/digest change is a separate, very small infra fix (`infrastructure/kubernetes/api-deployment.yaml` / `web-deployment.yaml` / `celery-deployment.yaml`, and `.github/workflows/docker-publish.yml`'s tagging strategy).

**Status: fixed (2026-07-28).** New `docs/operations/deployment-rollback-runbook.md`
plus a short pointer section in `docs/deployment/production-checklist.md`.

**Correction to this finding's own original text, found during
implementation (evidence contradicted the assumption above — reported per
the standing "zero assumptions" instruction rather than silently carried
forward):** the suggested "related sub-finding" about pinning to
immutable tags/digests turned out to already be solved, not a gap.
`.github/workflows/docker-publish.yml` was checked directly and already
tags every image with **both** `:latest` and the immutable
`${{ github.sha }}` on every push to `main`. `infrastructure/ci-cd/deploy.sh`
was checked directly and already deploys via `kubectl set image
deployment/erpx-api api=${REGISTRY}/erpx-api:${IMAGE_TAG}` where
`IMAGE_TAG` is that real git SHA, not `:latest` — the `:latest` value
visible in the static `infrastructure/kubernetes/*-deployment.yaml`
manifests is only the bootstrap placeholder for a cluster's first-ever
deploy, immediately overwritten by `deploy.sh` on every real deploy
after that. `kubectl rollout undo` and `kubectl rollout history`
therefore already operate on real, precise, immutable image tags today —
no infrastructure/CI change was needed, only the runbook documenting the
already-correct mechanism (and the separate, genuinely-still-needed
Alembic migration decision tree, which no tagging change would have
addressed anyway).

## 13. Accessibility

**Finding #14 (Medium):** No accessibility (WCAG 2.1 AA) tooling existed
in any of the 4 frontend apps (`apps/web`, `apps/student-portal`,
`apps/trainer-portal`, `apps/corporate-portal`) — confirmed: zero
`eslint-plugin-jsx-a11y`/`axe-core`/similar in any `package.json`, and
near-zero `aria-*`/`role=`/`alt=` attribute usage across all ~700
combined frontend source files.

**Status: Phase 1 (tooling + baseline) fixed (2026-07-28). Violations
themselves are not yet remediated — that is explicitly Phase 2, not part
of this change.**

### Tooling added

`eslint-plugin-jsx-a11y` (`^6.10.2`, compatible with this project's
`eslint ^8.57.1`) added to all 4 apps' `package.json` devDependencies.
Each app's `.eslintrc.cjs` gained `"plugin:jsx-a11y/recommended"` in
`extends`, `"jsx-a11y"` in `plugins`, and a `settings["jsx-a11y"].components`
map telling the plugin's rules to also check this project's own
`components/ui/*` wrapper components (`Button`, `Input`, `Textarea`,
`Select`, `Label`, `Table`) — not just raw HTML elements — since those
wrappers forward props onto real DOM elements via Radix's `Slot` pattern.

**Deliberately enabled at the plugin's real default severities, not
silenced.** `.github/workflows/ci.yml`'s frontend job runs `npm run build`
and `npm run test --if-present` — it never runs `npm run lint` — so
turning the rules on for real carries zero CI regression risk, and a
baseline measured against silenced/downgraded rules wouldn't be a real
baseline. Local `npm run lint --max-warnings 0` will now report these
violations where it previously reported none; this is the intended,
honest signal that a real gap exists, not a bug introduced by this change.

### Baseline: 24 violations across all 4 apps

| App | Violations | Categories |
|---|---|---|
| `apps/web` | 19 | 16× `jsx-a11y/label-has-associated-control`, 1× `jsx-a11y/heading-has-content`, 1× `jsx-a11y/click-events-have-key-events` + 1× `jsx-a11y/no-static-element-interactions` (same line) |
| `apps/student-portal` | 1 | 1× `jsx-a11y/heading-has-content` |
| `apps/trainer-portal` | 2 | 1× `jsx-a11y/heading-has-content`, 1× `jsx-a11y/label-has-associated-control` |
| `apps/corporate-portal` | 2 | 1× `jsx-a11y/heading-has-content`, 1× `jsx-a11y/label-has-associated-control` |
| **Total** | **24** | — |

**Violation categories, in order of prevalence:**

1. **`label-has-associated-control` (18 of 24, 75%)** — `<label>` elements
   in form dialogs/pages not programmatically associated with their input
   (missing `htmlFor`/nested control). Concentrated in `apps/web`'s
   accounting, HR/payroll, pentrix, and academic-ops feature forms —
   exactly the pattern one would expect from ~40 independently-built
   feature forms following a shared visual style but not a shared,
   enforced form-field component.
2. **`heading-has-content` (4 of 24, 17%)** — one shared root cause: line
   25 of `components/ui/card.tsx`, present identically in all 4 apps (the
   same file-copy pattern already confirmed for `client.ts`/`auth-store.ts`
   in the testing increments) — a `CardTitle` that can render with no
   accessible text content in some usage. Fixing this once and porting the
   fix to all 4 apps (matching the exact workflow already used for the
   auth-client tests) would resolve 4 of the 24 violations in one motion.
3. **`click-events-have-key-events` + `no-static-element-interactions` (2
   of 24, 8%)** — a single clickable non-interactive element (in
   `apps/web`'s `learning-paths-list-page.tsx`) with no keyboard
   equivalent — a real keyboard-navigation gap, not just a screen-reader
   gap.

### Validation performed

- `eslint` run directly (bypassing `--max-warnings 0`) against all 4 apps
  to establish the baseline counts above — real, unmodified rule
  severities.
- `tsc -b && vite build` — clean for all 4 apps, confirming the new
  ESLint config has no effect on TypeScript compilation or the Vite build
  (expected: ESLint is a separate static-analysis pass, not part of
  either pipeline).
- `vitest run` — all 4 apps' existing 8-test auth-client suites (32 tests
  total) still pass unchanged, confirming zero regression from the config
  change.
- No backend files touched; backend regression suite not re-run.

### Phase 2 (2026-07-28): shared `card.tsx` `CardTitle` fixed across all 4 apps

**Root cause:** `CardTitle` (`components/ui/card.tsx`, byte-identical
across all 4 apps — confirmed via direct `diff`, zero differences)
rendered `<h3 ref={ref} className={...} {...props} />` — `children` was
only ever carried implicitly through the `{...props}` spread, never
referenced explicitly in the JSX. `jsx-a11y/heading-has-content` performs
static analysis on the JSX tree and cannot verify a heading always has
accessible content when it's only ever provided via an opaque prop
spread, so it flagged the component's own definition.

**Fix:** destructured `children` explicitly out of `props` and rendered
it between the `<h3>` tags instead of relying on the spread alone. This
is a behavior-identical change for every existing, correctly-used
caller — React renders spread-in children the same way a component
renders explicitly-destructured-and-rendered children — so no caller
anywhere in any of the 4 apps needed to change. Verified live: the
login page's `CardTitle` ("Sign in to ERPX") still renders correctly as
an accessible heading in the DOM after the change (checked via the
browser's accessibility tree, not just static analysis).

**Files changed:** `apps/{web,student-portal,trainer-portal,corporate-portal}/src/components/ui/card.tsx`
(identical 8-line diff in each, confirmed post-change byte-identical
across all 4 apps again).

**Violations removed:** exactly 4 — one `heading-has-content` per app,
confirmed via direct `eslint` re-run before and after in every app.

| App | Before | After | Change |
|---|---|---|---|
| `apps/web` | 19 | 18 | -1 |
| `apps/student-portal` | 1 | **0** | -1 (fully clean) |
| `apps/trainer-portal` | 2 | 1 | -1 |
| `apps/corporate-portal` | 2 | 1 | -1 |
| **Total** | **24** | **20** | **-4** |

**Remaining 20 violations** (all pre-existing, untouched by this phase):
18× `jsx-a11y/label-has-associated-control` (`apps/web`: 16,
`apps/trainer-portal`: 1, `apps/corporate-portal`: 1), 1×
`jsx-a11y/click-events-have-key-events` + 1×
`jsx-a11y/no-static-element-interactions` (same line, `apps/web`'s
`learning-paths-list-page.tsx`) — both explicitly out of scope for this
phase per the strict "shared component only" instruction.

### Recommended remediation strategy (Phase 3+, not started)

1. Introduce one shared, accessible form-field pattern (label + control
   properly associated) and migrate the 18 `label-has-associated-control`
   sites to it — likely worth a small shared `FormField` wrapper in
   `components/ui/` rather than fixing each site's markup independently,
   since the underlying cause (labels not connected to controls) recurs
   identically across ~18 otherwise-unrelated feature forms. This is a
   materially larger change than Phase 2 (touches individual forms across
   many features, not one shared component) and should be scoped/approved
   as its own phase.
2. Fix the one keyboard-navigation gap in `learning-paths-list-page.tsx`
   (add a real `<button>`/keyboard handler instead of a clickable `<div>`).
3. Re-run the baseline after each phase to track the count down to zero
   for `jsx-a11y/recommended`, then evaluate `jsx-a11y/strict` as a
   further tightening once the current gap is closed.
4. This tooling-only/shared-component-only work does not address
   non-lintable accessibility concerns (color contrast, focus order,
   screen-reader testing with real assistive technology) — those need
   separate, likely manual or `axe-core`-in-Playwright-driven
   verification, out of scope for both Phase 1 and Phase 2.

## 14. Dependency Vulnerability Scanning

**Finding #15 (Medium):** No dependency vulnerability scanning existed
anywhere in `.github/workflows/*.yml` (confirmed: zero matches for
`pip-audit`/`npm audit`/`dependabot`/`snyk`/`trivy`/`safety`/`bandit`,
and no `.github/dependabot.yml` file) — a pre-existing item on
`docs/deployment/production-checklist.md`'s own Security checklist,
never implemented.

**Status: scanning tooling fixed (2026-07-28). The vulnerabilities it
found are NOT fixed — that is explicit, deliberate scope (no package
upgrades were made) — CI will correctly fail on the next backend push
and on all 4 frontend matrix legs until they are addressed separately.**

### What was added

- **Backend**: `pip-audit -r apps/api/requirements.txt` added to
  `.github/workflows/ci.yml`'s existing `backend` job (no new job).
  `pip-audit`'s own JSON output was verified directly to carry **no
  severity field at all** (only `id`/`fix_versions`/`aliases`/`description`)
  — there is no `pip-audit --audit-level` equivalent to npm's. New
  `.github/scripts/pip_audit_severity_gate.py` closes that gap: it
  resolves each finding's GHSA alias against the public OSV.dev API
  (`https://api.osv.dev/v1/vulns/{id}`), which reliably exposes a real
  `database_specific.severity` field (verified empirically against this
  project's actual findings — `MODERATE`, `HIGH`, `CRITICAL` all
  observed) for GHSA-sourced advisories, and exits non-zero **only**
  when a `CRITICAL`/`HIGH` finding is present. `pip-audit`'s own exit
  code is deliberately absorbed (`|| true`) so it never blocks the
  build directly — the gate script is what determines pass/fail. The
  full report is uploaded as a build artifact regardless of severity.
- **Frontend**: `npm audit` added to the existing `frontend` matrix job
  (already covers all 4 apps — `web`, `student-portal`, `trainer-portal`,
  `corporate-portal` — no new job needed). Two steps: a full-severity
  `npm audit --json` report (always uploaded as an artifact,
  non-blocking), and `npm audit --audit-level=high` as the actual gate —
  npm's own native flag already does exactly what was asked (exits
  non-zero only for `high`/`critical`), no custom severity parsing
  needed.
- Neither `--fix` nor `npm audit fix` was used anywhere — no package was
  upgraded, replaced, or pinned by this change.

### Real findings surfaced (informational — not remediated in this change)

**Backend** (`apps/api/requirements.txt`), via the actual gate run against
this repository:

| Package | Installed | Vulnerability | Severity | Fix version | Status |
|---|---|---|---|---|---|
| `python-jose` | 3.3.0 | PYSEC-2024-232 / CVE-2024-33663 | **CRITICAL** | 3.4.0 | **Investigated, deliberately not upgraded** — see below |
| `python-multipart` | ~~0.0.9~~ **0.0.32** | PYSEC-2026-1852, -1851, -3036, -3039 | **HIGH** (×4) | 0.0.18–0.0.30 | **Fixed (2026-07-29)** |
| `starlette` | 0.38.6 | PYSEC-2026-249, -1943, -2281 | **HIGH** (×3) | 0.40.0–1.1.0 | Open — transitive via `fastapi`, not yet evaluated |
| `ecdsa` | 0.19.2 | PYSEC-2026-1325 | **HIGH** | (no fix published yet) | Open — cannot be fixed by upgrading; no version resolves it |

Plus several `MODERATE`/`LOW` findings (`python-jose`, `python-dotenv`,
`aiosmtplib`, `pytest`, `starlette`) that do not block the build.

**Frontend** — **correction (2026-07-29):** the text below originally
attributed all 17 findings to `react-router-dom`. Re-running `npm audit
--json` for real against all 4 apps and reading each finding's own
`isDirect`/`via`/`fixAvailable` fields (not just the summary counts) shows
that description was wrong about the root cause; corrected here with the
verified breakdown.

All 4 apps' `package-lock.json` resolve to byte-identical dependency
trees (confirmed via a direct diff of each app's full `npm audit --json`
output, not just matching totals), so the finding is genuinely identical
across `apps/web`, `apps/student-portal`, `apps/trainer-portal`, and
`apps/corporate-portal`: 17 total vulnerabilities per app (5 moderate, 11
high, 1 critical).

| Package | Severity | Direct/Transitive | Advisory | Fix path |
|---|---|---|---|---|
| `vitest` | ~~CRITICAL~~ **FIXED (2026-07-29)** | Direct (`devDependency`) | GHSA-5xrq-8626-4rwp — arbitrary file read/execute when the Vitest UI server is listening | **`2.1.9 → 3.2.6`** — patched at exactly `3.2.6`, non-breaking, no Vite bump; see the dedicated subsection below |
| `eslint` | HIGH | Direct (`devDependency`) | via `@eslint/eslintrc`/`file-entry-cache`/`minimatch` chain | `eslint@10.8.0` — **breaking** |
| `@eslint/eslintrc` | HIGH | Transitive (via `eslint`) | via `minimatch` | requires `eslint@10.8.0` — **breaking** |
| `@humanwhocodes/config-array` | HIGH | Transitive (via `eslint`) | via `minimatch` | requires `eslint@10.8.0` — **breaking** |
| `file-entry-cache` | HIGH | Transitive (via `eslint`) | via `flat-cache` | requires `eslint@10.8.0` — **breaking** |
| `flat-cache` | HIGH | Transitive (via `eslint`) | via `rimraf` | requires `eslint@10.8.0` — **breaking** |
| `glob` | HIGH | Transitive (via `eslint`) | via `minimatch` | requires `eslint@10.8.0` — **breaking** |
| `rimraf` | HIGH | Transitive (via `eslint`) | via `glob` | requires `eslint@10.8.0` — **breaking** |
| `eslint-plugin-jsx-a11y` | HIGH | Direct (`devDependency`, added by finding #14's a11y tooling) | via `minimatch` | `eslint-plugin-jsx-a11y@6.4.1` — **breaking** |
| `minimatch` | HIGH | Transitive (via `eslint-plugin-jsx-a11y`) | via `brace-expansion` | requires `eslint-plugin-jsx-a11y@6.4.1` — **breaking** |
| `brace-expansion` | HIGH | Transitive (via `eslint`/`eslint-plugin-jsx-a11y`) | GHSA-mh99-v99m-4gvg — DoS via unbounded expansion length, vulnerable range `<=5.0.7` | **corrected 2026-07-29 — no working non-breaking fix exists**; see the dedicated subsection below |
| `vite` | HIGH | Direct (`devDependency`) | via `esbuild` | `vite@8.1.5` — **breaking** |
| `esbuild` | Moderate | Transitive (via `vite`) | dev-server request/path-traversal advisories | requires `vite@8.1.5` — **breaking** |
| `@vitest/mocker` | ~~Moderate~~ **FIXED (2026-07-29)** | Transitive (via `vitest`) | via `vite` | resolved as a side-effect of the `vitest 2→3.2.6` upgrade (`@vitest/mocker@3.2.6` no longer flagged) |
| `vite-node` | ~~Moderate~~ **FIXED (2026-07-29)** | Transitive (via `vitest`) | via `vite` | resolved as a side-effect of the `vitest 2→3.2.6` upgrade (`vite-node@3.2.4` no longer flagged) |
| `react-router` | Moderate | Transitive (via `react-router-dom`) | GHSA-wrjc-x8rr-h8h6 (open redirect), GHSA-337j-9hxr-rhxg (SSR hydration constructor injection) | fixed in `react-router@7.18.0` — **breaking** (major, v6→v7) |
| `react-router-dom` | Moderate | Direct (`^6.26.2` in `package.json`, resolves to `6.30.4`) | GHSA-jjmj-jmhj-qwj2 — open redirect leading to XSS | **no fix exists for this package name at all** — verified via a real `npm audit fix --force --dry-run`, which left all 17 findings, including this one, completely unchanged; the upstream advisory's own `first_patched_version` for `react-router-dom` specifically is `None` (only the separate `react-router` package name got a fix, in `7.13.0`/`7.18.0`) — resolving this requires migrating off the deprecated `react-router-dom` package to the unified `react-router` package (the v6→v7 rewrite), not any version bump |

**Corrected finding:** `react-router`/`react-router-dom` account for only
the **3 Moderate** findings, not the 11 High/1 Critical the earlier text
attributed to them. Every High and the one Critical finding trace to the
`eslint`/`vite`/`vitest` **devDependency toolchain** — build-time and
test-time tooling only, not shipped in the production browser bundle —
introduced/expanded by finding #14's `eslint-plugin-jsx-a11y` addition
and the pre-existing `vite`/`vitest` pins. `npm audit --audit-level=high`
(the CI gate added by this same finding) is failing on the toolchain
findings, not on `react-router-dom`.

**Post-fix state (2026-07-29):** after the `vitest 2→3.2.6` upgrade below,
each app's `npm audit` reports **14 total (0 critical, 11 high, 3
moderate)**, down from the 17 (1 critical, 11 high, 5 moderate) baseline
above — the 1 CRITICAL plus 2 of the 5 Moderate findings resolved, 0 new
introduced.

### `vitest` (CRITICAL) — fixed (`2.1.9 → 3.2.6`)

**Root cause:** GHSA-5xrq-8626-4rwp ("when the Vitest UI server is
listening, an arbitrary file can be read and executed") — advisory
vulnerable range `<3.2.6` (and separately `>=4.0.0 <4.1.0`). All 4
frontend apps ran `vitest@2.1.9`, inside that range. (ERPX doesn't even
run the Vitest UI server — the `test` script is `vitest run`, no UI, no
watch — so the attack surface wasn't active here, but the vulnerable code
was still present in the installed tree.)

**Why `3.2.6` specifically** (not latest `4.1.10`): `3.2.6` is the exact
first-patched version for the `<3.2.6` range and is the highest version
reachable **without** forcing a coupled Vite major upgrade. `vitest@4.x`
peer-requires `vite@^6 || ^7 || ^8`, which would drag the whole build
toolchain into a bundler-engine change (Vite 8 replaces Rollup/esbuild
with Rolldown/Oxc) — out of scope and high-risk. `vitest@3.2.6`'s own vite
dependency range is `^5.0.0 || ^6.0.0 || ^7.0.0-0`, so the existing
`vite@5.4.21` satisfies it unchanged. Full pre-upgrade compatibility
investigation (all 13 documented Vitest 3.0 breaking changes checked
individually against real repo usage — none apply; the test files use only
`describe`/`it`/`expect`/`beforeEach`/`afterEach`/`vi.fn`/`vi.restoreAllMocks`/`.rejects.*`,
all stable across 2→3) was completed and approved before this
implementation.

**What changed:** `"vitest": "^2.0.5"` → `"vitest": "3.2.6"` in all 4
apps' `package.json`, and the corresponding `package-lock.json` updates.
A real `npm install` was run per app; the resulting lockfile diff is
confined to the vitest family and its internal helpers (`vitest`,
`@vitest/*`, `vite-node@3.2.4`, `pathe`, `tinyrainbow`, `tinyspy`,
`strip-literal`, `js-tokens`, `picomatch`, `@types/chai`,
`@types/deep-eql`). Verified directly that the lockfiles' `vite`, `react`,
and `eslint` entries are **unchanged** (resolved `vite@5.4.21`,
`react@18.3.1`, `eslint@8.57.1` in all 4 apps post-install) — no unrelated
dependency drift, no `npm audit fix --force` used.

**Validation (all 4 apps, real runs):**
- `vitest run`: **8/8 tests pass** per app (32 total) — the existing
  auth-client interceptor suite, unchanged.
- `tsc -b`: clean.
- `vite build`: succeeds.
- `npm audit`: **14 findings (0 critical / 11 high / 3 moderate)** per
  app, down from 17 (1/11/5). GHSA-5xrq-8626-4rwp confirmed absent; the
  `@vitest/mocker` and `vite-node` Moderate findings also cleared as a
  side-effect. **Zero new vulnerabilities introduced.**

The 11 HIGH (the `eslint`/`vite` chain) and 3 remaining Moderate
(`esbuild`, `react-router`, `react-router-dom`) are untouched by this
change — all require the separately-scoped breaking upgrades already
documented above and were explicitly out of scope.

### `brace-expansion` (HIGH) — attempted, reverted; not actually fixable without a breaking change

**Correction (2026-07-29):** the previous version of this document
characterized `brace-expansion`'s fix as "a genuine non-breaking patch,"
based on `npm audit fix --dry-run`'s change list showing only
`brace-expansion` itself would be touched, with no `package.json` or
major-version changes. That was true as far as it went, but incomplete —
it never checked whether the resulting versions actually cleared the
advisory's vulnerable range. They don't, for 5 of the package's 6
installed instances.

**Attempted, with real validation, in this task:** `npm audit fix` (no
`--force`) was run for real in all 4 apps. It changed only
`package-lock.json` in each (confirmed via `git status` — zero
`package.json` changes, matching the task's own gate), bumping
`brace-expansion` from `1.1.16` → `1.1.17` in 5 of 6 installed instances
(the ones nested under `eslint@8.57.1`/`eslint-plugin-jsx-a11y@6.10.2`,
via their shared `minimatch@3.1.5` dependency) and from `5.0.7` → `5.0.8`
in the 6th (nested under `@typescript-eslint/parser`'s `minimatch@10.2.5`,
an unrelated, newer major line of `minimatch` that happens to share the
`brace-expansion` package name for its own bundled helper).

**Root cause of why this doesn't work:** GHSA-mh99-v99m-4gvg's own
published `vulnerable_version_range` is `<=5.0.7` — a single range
spanning both the old `1.x` and current `5.x` release lines of this
package. `1.1.17` satisfies `<=5.0.7` numerically (1 < 5), so it is
**still inside the vulnerable range** despite being a newer patch within
its own `1.x` line — only the `5.0.8` bump (the 6th instance) actually
clears it. The other 5 instances can't reach `5.0.8` because
`minimatch@3.1.5` (itself pulled in by `eslint@8.57.1` and
`eslint-plugin-jsx-a11y@6.10.2`, both otherwise unrelated to this
finding) declares a hard `^1.1.7` dependency on `brace-expansion` in its
own `package.json` — the same class of transitive-constraint trap already
seen twice on the backend this session (`python-jose`/`pyasn1`,
`fastapi`/`starlette`): the nominal "fix" version is outside the range
the actual installed dependent permits, and getting there requires
bumping `minimatch` itself, which requires bumping `eslint`/
`eslint-plugin-jsx-a11y` past a major version — exactly the breaking
change this task was explicitly prohibited from making.

**Verified, not assumed:** a real post-fix `npm audit --json` was run in
all 4 apps after applying the fix — the reported count was **unchanged**
at 17 total (5 moderate, 11 high, 1 critical) in every app, and
`brace-expansion` itself still appeared as an active finding. This
directly contradicts what a "fix" should do, so the change was reverted
(`git checkout -- package-lock.json` in all 4 apps, followed by `npm
install` to resync `node_modules`) rather than committed. Confirmed clean
via `git diff --shortstat` after reverting: zero real content
differences from the pre-existing committed lockfiles (only git's own
LF/CRLF line-ending metadata warning, no actual changes), and `npm ls
brace-expansion` confirmed all 4 apps are back to their original
`1.1.16`/`5.0.7` resolved versions.

**Status: no code/lockfile change made.** This finding requires the same
`eslint` 8→10 / `eslint-plugin-jsx-a11y` major-version upgrade as the
other `eslint`-chain HIGH findings — it cannot be resolved in isolation
as a small, low-risk patch the way it first appeared to be.

### `python-jose` (CRITICAL) — investigated, upgrade deliberately deferred

Attempted first as the single highest-severity finding. **Blocked, not
implemented**: `python-jose[cryptography]==3.4.0`'s own published PyPI
metadata declares a hard constraint `pyasn1<0.5.0,>=0.4.1`. Installing it
forces pip to *downgrade* the already-present `pyasn1` (0.6.4 → 0.4.8) —
confirmed via a real `pip install` and a before/after `pip-audit` diff —
and that older `pyasn1` carries **5 separate HIGH-severity vulnerabilities**
of its own. Upgrading `python-jose` as published would trade 1 CRITICAL
for 5 HIGH findings, not a clean fix. Reverted; tracked as a known,
deliberate risk pending a decision on whether to override `pyasn1`'s
version against `python-jose`'s own declared (and effectively unmaintained
upstream) constraint, or migrate off `python-jose` entirely — both
explicitly out of scope without further approval.

### `python-multipart` (HIGH ×4) — fixed

`0.0.9` → `0.0.32` (`apps/api/requirements.txt`). Direct dependency (no
other installed package requires/constrains it — confirmed via `pip show`),
and `fastapi==0.115.0`'s own metadata declares only an open-ended
`python-multipart>=0.0.7` — no upper bound, no transitive-constraint trap
like `python-jose`/`pyasn1`. Verified clean via a real `pip-audit`
before/after diff: all 4 HIGH findings gone, **zero new vulnerabilities
introduced**. Zero uses of `python-multipart`'s own API directly anywhere
in this codebase (`grep` confirmed) — it's consumed only internally by
FastAPI/Starlette's `File`/`Form`/`UploadFile` support, which was verified
directly (not just inferred from the changelog) with a real
`fastapi.testclient.TestClient` request exercising simultaneous file
upload + form field parsing — response matched exactly on filename,
content type, byte-for-byte file content, and form field value.

**Full validation, including the real backend regression suite** (initially
blocked by a local Postgres infrastructure fault unrelated to this change
— see below — then re-run to completion once fixed): **257/257 passing**,
`pip-audit` re-confirmed clean post-fix.

**Local infrastructure note (not a code issue):** the standalone Postgres
cluster used for local test runs (`pgdata_standalone/`) turned out to have
no explicit `port` set in `postgresql.conf` — it silently defaulted to
Postgres's standard `5432`, which was already occupied by an unrelated,
already-running Postgres Windows service. Every earlier "Permission
denied" bind failure this session was a misleading symptom of that same
underlying port conflict (an IPv6 `::1` bind attempt failing first
obscured the real IPv4 `5432`-already-in-use error in the log). Fixed by
explicitly setting `port = 5433` in `postgresql.conf`, matching what this
project's `DATABASE_URL`/test configuration has always expected. This is
a local dev-environment fix only — no repository files were changed by it.

### Recommended remediation (separate follow-up, not this change)

1. `starlette` (HIGH ×3) is the next reasonable candidate — but it's
   transitive via `fastapi`, so its own declared constraint needs checking
   first (the same class of check that caught the `python-jose`/`pyasn1`
   trap) before assuming it's safe to bump directly.
2. `ecdsa` (HIGH) has no available fix version at all — upgrading is not
   an option; the only paths are removing the dependency (`python-jose`
   pulls it in) or accepting the risk, tracked but not actionable via a
   simple version bump.
3. The frontend `eslint`/`vite`/`vitest` toolchain findings (11 High, 1
   Critical — corrected 2026-07-29, see the Frontend breakdown and the
   `brace-expansion` subsection above) are the higher-value next
   candidate — but **all 12 of them, including `brace-expansion`, require
   the same breaking `eslint` 8→10/`eslint-plugin-jsx-a11y`/`vite`/`vitest`
   major-version upgrade**; a `brace-expansion`-only non-breaking fix was
   attempted and verified not to work (see above). This needs a single
   scoped upgrade task, evaluated for breaking changes the same way
   `starlette` was.
   `react-router`/`react-router-dom` (3 Moderate, not High/Critical) is
   lower priority by severity, and its one XSS-adjacent finding
   (`react-router-dom`) has no fix at all short of the v6→v7 package
   migration — its own separate, larger scoped task regardless of
   priority ordering.
4. Once addressed, re-run both gates locally to confirm a clean pass
   before the next CI run depends on it.

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
