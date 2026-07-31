# ERPX v1.0.0 — Release Notes

**Release date:** 2026-08-01
**Release commit:** the tagged `v1.0.0` commit (see docs/release/GIT_TAG_INSTRUCTIONS.md)
**Image:** `ghcr.io/gir-technologies/erpx-api:latest` (and `:<git-sha>`)
**Readiness:** GO for production (98/100) — no Critical/High/Medium blockers.

---

## Overview

ERPX v1.0.0 is the first production release of the GIR Technologies unified
business platform: **ERP + LMS + CRM + Accounting + Pentrix**, delivered as a
multi-tenant (organization-scoped) FastAPI backend with React frontends.

## Highlights

- **48 business modules** covering CRM, Students, Courses & LMS, Examinations,
  Pentrix (cyber-lab), Accounting, HR & Payroll, Inventory/Assets/Procurement,
  Corporate services (projects, contracts, tickets, AMC, SOC, VAPT), Marketing,
  Administration, and operational modules (Backups, Integrations, Monitoring,
  Notifications, Workflow/Approvals, and more).
- **Four frontends:** main web app + student, trainer, and corporate portals,
  with route-based lazy loading, code splitting, and enforced accessibility.
- **Financial integrity:** double-entry accounting with journal balancing
  enforced at the service layer; GST/TDS; invoices/receipts/payments; scheduled
  reports.
- **Concurrency safety:** coupon redemption and inventory stock movements are
  serialized with row-level locks to prevent over-redemption / stock oversell.
- **Enterprise plumbing:** Redis response caching, OpenTelemetry tracing, Sentry,
  Prometheus metrics, structured logging, Celery jobs with retry/backoff, MinIO
  object storage, reversible Alembic migrations, hardened multi-stage non-root
  Docker image, Kubernetes manifests (HPA + readiness/liveness/startup probes),
  and Terraform.

## Quality gates (at release commit)

- Backend automated tests: **309 passing** (304 unit/api/integration/security +
  5 performance), 0 regressions.
- Alembic migrations: **38 revisions, single head (0038), all reversible.**
- CI: backend tests + coverage + migration check + dependency-vulnerability
  gating; frontend build+test across all 4 apps; image publish gated on CI.

## Upgrade / installation

This is the initial release. See `docs/release/DEPLOYMENT.md` for full
deployment instructions and `docs/deployment/production-checklist.md` for the
evidence-cited environment checklist.

## Breaking changes

None (initial release).

## Deferred to a future release (by decision)

- **Global search** — Elasticsearch is provisioned but not wired into an in-app
  search API/UI for 1.0.0 (post-1.0).
- **Pentrix lab provisioning** — ships with the documented `StubProvisioner`;
  real environment spin-up (Docker/Kubernetes/cloud) is a post-1.0 infra decision.
- **Global rate limiting** — enforced per-route plus at the ingress/API-gateway;
  no in-app global middleware.

## Known minor items (non-blocking; planned for 1.0.x)

- Minor list-response envelope variance across a few endpoints.
- Frontend automated-test coverage is light outside the main web app.

## Credits

Built by GIR Technologies. Production hardening and release validation performed
across audit findings #1–#33 (see `docs/project-hardening-audit.md`).
