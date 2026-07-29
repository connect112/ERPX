# ERPX Production Readiness Audit

Date: 2026-07-27
Scope: platform-wide cross-cutting concerns (security, observability, deployment,
background jobs, CI/CD) — not a re-audit of individual business-module CRUD
correctness, which was already verified module-by-module earlier in this
project's development (197/197 backend automated tests passing at time of
writing).

Every finding below is backed by an exact file path. Nothing here is inferred
or assumed — each item was read directly from the source.

## Executive summary

The platform-wide infrastructure is substantially more mature than a typical
"MVP with CRUD forms" — real automatic audit logging, real Kubernetes
manifests with correctly-differentiated liveness/readiness/startup probes and
HPA, real Terraform (including Multi-AZ toggles for RDS + ElastiCache), a real
monitoring stack (Prometheus + Grafana + alert rules), and a real two-provider
AI integration that fails closed without credentials rather than mocking a
response. This is not scaffolding — it's genuinely production-grade plumbing.

Against that, a handful of concrete, verifiable gaps exist. One of them
(#1 below) is not a "missing feature" — it is an operational bug that would
cause a real production outage on first Kubernetes deploy if not caught, and
should be treated as the top priority.

## 1. What is genuinely enterprise-ready (verified)

| Capability | Evidence |
|---|---|
| Automatic, tamper-consistent audit logging for every module (including future ones) via SQLAlchemy session events — no per-service instrumentation required | `modules/audit/hooks.py` |
| Consistent JSON error envelope, no stack traces leaked, request-ID correlation | `apps/api/app/core/exception_handlers.py` |
| Security headers (nosniff, frame-deny, referrer policy, permissions policy, conditional HSTS) | `apps/api/app/middleware/security_headers.py` |
| Structured logging, gzip compression, CORS, global rate limiting, Prometheus `/metrics` | `apps/api/app/main.py` |
| Account lockout after N failed logins (real, not just config) | `modules/authentication/repository.py`, `service.py` |
| RBAC: per-endpoint `require_permissions()`, Super Admin bypass, Administrator/Staff tiers, sensitive-ops-only permissions (backups, integrations, monitoring, transcripts) deliberately excluded from Staff | `modules/authorization/service.py` |
| Real two-provider AI integration (Anthropic + OpenAI-compatible), fails closed with a clear error if unconfigured — not a stub | `packages/ai/client.py` |
| Real background jobs with exponential-backoff retry for customer-facing sends (WhatsApp/SMS reminders) | `modules/crm/followups/tasks.py` |
| Real scheduled reports: CSV/Excel/PDF export + email delivery on a cron schedule | `modules/reports/tasks.py`, `packages/reports/exporters.py` |
| Real Kubernetes manifests: resource requests/limits, 3 differentiated probe types, HPA (CPU+memory), Prometheus scrape annotations, `terminationGracePeriodSeconds` | `infrastructure/kubernetes/api-deployment.yaml` |
| Real Terraform with Multi-AZ toggle for both RDS and ElastiCache | `infrastructure/terraform/database.tf` |
| Real monitoring stack: Prometheus scrape config, Grafana dashboards + datasources, alert rules | `infrastructure/monitoring/` |
| Reversible migrations — all 36 Alembic revisions have real `downgrade()` bodies, none are `pass`-only | `apps/api/alembic/versions/` |
| CI runs real backend tests with coverage + Alembic migration check on every push/PR | `.github/workflows/ci.yml` |
| Image publish gated on CI success (never builds from an unvalidated commit) | `.github/workflows/docker-publish.yml` |
| Detailed, evidence-cited production checklist already exists | `docs/deployment/production-checklist.md` |

## 2. What is "just CRUD" (not a criticism — plenty of business domains genuinely only need this)

Straightforward create/read/update/delete modules without workflow, background
processing, or external I/O — e.g. Course Categories, Departments &
Designations, Coupons, Item Categories, Asset Categories. These don't need
audit-workflow complexity to be "done"; they're correctly scoped as simple
CRUD and were verified working end-to-end (backend tests + browser
verification) earlier in the project.

## 3. Concrete gaps (verified, in priority order)

### 🔴 High — operational bug, not a missing feature

**#1. The Kubernetes readiness probe will never pass in a real deployment that hasn't stood up Elasticsearch, even though nothing in the app uses Elasticsearch yet.**

`/api/v1/health/ready` (`apps/api/app/api/v1/health.py`) computes
`all_healthy = all(checks.values())` across `database`, `redis`, `storage`,
**and `search`** (an Elasticsearch ping). `infrastructure/kubernetes/api-deployment.yaml`
wires exactly this endpoint as the `readinessProbe`. Since no Elasticsearch
service exists in `docker-compose.yml`'s default profile or is referenced
anywhere else as actually required, deploying to Kubernetes today — before
anyone builds a search feature — means every pod fails its readiness check
forever and receives zero traffic from the Service. This isn't hypothetical:
I verified `packages/search/` is empty (no code calls Elasticsearch anywhere
outside this health check).

**Fix options** (not yet applied — flagged for your decision, since you asked
for an audit, not implementation): make the `search` check informational only
(don't fail readiness on it) until a real search feature exists, or stand up
Elasticsearch as a required dependency now. I'd recommend the former.

### 🟠 Medium

**#2. `apps/web`'s `npm run test` (vitest) is wired into `package.json` and CI but zero `.test.ts`/`.test.tsx` files exist anywhere in the app** — only 3 Playwright e2e specs (`apps/web/e2e/*.spec.ts`), which run via the separate `test:e2e` script. The CI "Run frontend tests" step is currently running a test command against an empty suite.

**#3. `student-portal`, `trainer-portal`, and `corporate-portal` have no `test` script in `package.json` at all, and `.github/workflows/ci.yml`'s `frontend` job only builds/tests `apps/web`.** A breaking change in any of the other 3 frontend apps would merge to `main` and publish a Docker image without CI ever touching it.

**#4. `Dockerfile` (`apps/api/Dockerfile`) is single-stage and has no `USER` directive** — `build-essential`/`gcc` ship into the final runtime image (larger attack surface, larger image), and the container runs as root. Has a real `HEALTHCHECK`, just not hardened otherwise.

### 🟡 Low

**#5. Global rate limiting (`slowapi`, `RATE_LIMIT_DEFAULT` = 100/minute) applies uniformly to every endpoint** — login and password-reset get the same limit as a paginated list endpoint. Account lockout (finding in §1) is a real compensating control, but per-endpoint throttling on auth routes specifically is still standard defense-in-depth for a system handling payroll/financial data.

**Status: fixed (2026-07-29).** See `docs/project-hardening-audit.md`
finding #9 for full detail — `/auth/register`, `/auth/login`,
`/auth/refresh`, `/auth/forgot-password`, `/auth/reset-password`, and
`/auth/resend-verification` now each carry their own tighter per-route
limit (10/minute, 10/minute, 20/minute, 5/minute, 5/minute, 5/minute
respectively); every other endpoint, including the paginated list
endpoints this finding contrasted against, still uses the unchanged
100/minute global default.

**#6. Two Celery tasks have no retry/backoff**: `accounting.mark_overdue_invoices` and `reports.run_due_scheduled_reports` (`modules/accounting/invoices/tasks.py`, `modules/reports/tasks.py`) — contrast with `crm.followups.send_whatsapp_reminder`/`send_sms_reminder`, which do retry with backoff. Lower severity because both are idempotent and naturally self-heal on the next scheduled run, but a transient DB hiccup means slower recovery and no retry-exhaustion alerting.

**#7. Global/cross-entity search**: `ELASTICSEARCH_URL` is configured and Elasticsearch is provisioned in `docker-compose.yml` and Terraform-adjacent infra, but `packages/search/` is empty — no indexing, no search endpoint, no UI. This is the same finding reported earlier this session; repeated here for completeness since it's directly related to finding #1.

## Recommended order to close these

1. Fix #1 first — it's the only one that would actually break a production deploy, and the fix is small (change one boolean's contribution to the readiness check).
2. #3, then #2 — CI blind spots compound over time; cheaper to close now than after more feature work lands on the unwatched apps.
3. #4 — Docker hardening, self-contained, low risk.
4. #5, #6 — tuning/polish, no urgency.
5. #7 — only worth doing when a real search requirement exists; don't build it speculatively.
