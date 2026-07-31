# Changelog

All notable changes to ERPX are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-01

First production release of the ERPX platform (ERP + LMS + CRM + Accounting +
Pentrix) for GIR Technologies. Certified GO for production after a full-stack
release validation (no Critical/High/Medium blockers).

### Added — Platform capabilities
- Multi-tenant (organization-scoped) FastAPI backend spanning 48 business modules:
  CRM (leads, enquiries, follow-ups, counselling, admissions), Students, Courses &
  LMS (enrollment, progress, assignments, assessments, certificates, badges,
  bookmarks, transcripts), Examinations (question bank, exams, evaluation,
  practicals, viva, results), Pentrix (labs, challenges, flags, hints, lab
  instances, achievements, leaderboard, certifications), Accounting (chart of
  accounts, journals, customers, vendors, GST, TDS, bank, invoices, receipts,
  expenses, payments, reports), HR & Payroll, Inventory / Assets / Procurement,
  Corporate (clients, projects, quotations, contracts, tickets, AMC, SOC, VAPT,
  reports), Marketing (campaigns, coupons, landing pages, referrals, analytics),
  Administration (organizations, branches, users, roles, settings), plus
  Workshops, Hackathons, Placements, Internships, Alumni, Media, Workflow &
  Approvals, Notifications, Communication, Events, Backups, Integrations,
  Monitoring.
- React frontends: main web app plus student, trainer, and corporate portals.
- Real integrations: MinIO object storage (presigned URLs), two-provider AI
  (Anthropic + OpenAI-compatible, fail-closed), Celery jobs (WhatsApp/SMS
  reminders, scheduled reports, overdue-invoice sweep), Redis.

### Added — Production hardening (audit findings #9–#33)
- **Security:** per-route rate limiting on the pre-auth surface and the anonymous
  landing-page view beacon; JWT with pinned algorithm and a startup guard that
  rejects placeholder/short secrets; per-endpoint RBAC; account lockout; security
  headers; Sentry error aggregation (PII-scrubbed, env-gated).
- **Observability:** OpenTelemetry distributed tracing (FastAPI/SQLAlchemy/Redis/
  Celery/HTTPX, `trace_id`/`span_id` in logs), Prometheus `/metrics`, structured
  logging with request-ID correlation.
- **Performance:** Redis response caching for read-only aggregates; frontend
  route-based lazy loading + code splitting; SQL-side aggregation and N+1
  elimination across Accounting AR/AP aging, LMS transcripts, Corporate VAPT
  portfolio, Marketing analytics, and the Inventory low-stock report; composite
  DB indexes (EXPLAIN-verified).
- **Reliability:** retry/backoff on all scheduled Celery tasks; reversible Alembic
  migrations (38 revisions, all with real `downgrade()` bodies).
- **Accessibility:** `eslint-plugin-jsx-a11y` enforced across all frontend apps
  (`jsx-a11y/recommended` clean).

### Fixed
- **Data integrity (concurrency):** closed the coupon usage-limit TOCTOU and the
  inventory stock-oversell TOCTOU by serializing the affected operations with
  `SELECT ... FOR UPDATE` row locks.
- **Runtime crash:** inventory `get_stock_level` raised `TypeError` (`Decimal *
  float`) whenever a receipt existed; normalized to float.
- **Deployment (Critical):** the published API Docker image was not
  self-contained — it was built from the `apps/api` context, which excludes the
  repo-root `modules/` and `packages/`, so the image shipped empty modules and
  crash-looped (`ModuleNotFoundError`). Now built from the repository-root context
  and verified to boot standalone.
- **Auth bootstrap (Critical):** a fresh `docker compose up` could not log in —
  the `SEED_SUPERADMIN_*` variables never reached the container and nothing ran
  migrations/seed on startup. Added a guarded entrypoint that runs
  `alembic upgrade head` + the idempotent seed, and wired the variables through
  compose.
- **Auth bootstrap:** the seeded Super Admin had no organization, so org-scoped
  endpoints (e.g. `/audit`) returned HTTP 422. The seed now attaches the Super
  Admin to a default "System" organization via a user profile (idempotent).

### Security
- No hardcoded secrets in tracked source; Kubernetes injects secrets via
  `secretKeyRef` (`erpx-secrets`). ORM-only data access (no raw SQL/injection).

### Known minor items (non-blocking, targeted for 1.0.x)
- Empty untracked `apps/api/{modules,packages}` bind-mount stub directories.
- Minor list-response envelope variance across a few endpoints.

[1.0.0]: https://github.com/gir-technologies/erpx/releases/tag/v1.0.0
