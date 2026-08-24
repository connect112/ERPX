# ERPX Production Readiness Checklist

## Before first deploy

- [ ] `JWT_SECRET_KEY` set to a real random 64-character value (never the `change_me_...` default in `app/core/config.py`)
- [ ] `DATABASE_URL`, `REDIS_URL` point at managed services, not the docker-compose container names
- [ ] `AI_API_KEY` set if AI features (`modules/ai`) are enabled — without it, every AI endpoint returns 503 (`packages/ai/client.py` fails closed rather than silently no-opping)
- [ ] SMTP credentials set — without them, verification/password-reset/scheduled-report emails silently fail (`EmailService.send` catches and logs, returns `False`, never raises)
- [ ] `infrastructure/kubernetes/secret.yaml` created from `secret.yaml.example` and applied — never committed
- [ ] `CORS_ORIGINS` restricted to the real frontend domain(s), not `localhost`
- [ ] `ENVIRONMENT=production` — this disables `/api/docs` and `/api/redoc` (see `app/main.py`) and enables the HSTS header (`SecurityHeadersMiddleware`)
- [ ] Alembic migrations applied (`alembic upgrade head`) — run as a one-off Job (`infrastructure/ci-cd/deploy.sh`), never baked into a Deployment's startup command
- [ ] `seed_default_rbac()` run once against the production database so the default permission/role catalog exists (see `modules/authorization/service.py`)
- [ ] At least one superuser account created (bypasses permission checks — see `modules/authorization/dependencies.py`)
- [ ] `apps/api/scripts/seed.py`'s `seed_pentrix_program()` run once so the Pentrix-share provisioning endpoint has an org/course to resolve into (see `modules/provisioning/service.py`)
- [ ] `ERPX_INTERNAL_SERVICE_SECRET` set to a real random value matching Pentrix-share's own copy of it — without it, `POST /api/v1/internal/provisioning/students` fails closed (401) on every call, not silently open (see `modules/provisioning/dependencies.py`)
- [ ] `STUDENT_PORTAL_URL` set to the real `apps/student-portal` origin — otherwise a provisioned student's "set your password" email links at `localhost`

## Infrastructure

- [ ] Postgres: automated backups enabled, Multi-AZ for production (`infrastructure/terraform/database.tf` sets this via `enable_multi_az`)
- [ ] Redis: persistence/replication appropriate for Celery task durability — a lost broker mid-task means a lost payroll run or scheduled report
- [ ] MinIO/S3: bucket versioning + encryption enabled; not publicly readable
- [ ] Celery beat: **exactly one replica** — running two double-fires every scheduled task (overdue-invoice sweep, depreciation reminders, scheduled report emails). `infrastructure/kubernetes/celery-deployment.yaml` pins this via `replicas: 1` + `strategy: Recreate`.
- [ ] TLS terminated at the ingress/load balancer; `Strict-Transport-Security` only applies once this is true

## Rollback

Full procedure: `docs/operations/deployment-rollback-runbook.md`.

- [ ] Whoever is on-call knows `kubectl rollout undo deployment/erpx-api -n erpx` (and the equivalent for `erpx-celery-worker`/`erpx-celery-beat`/`erpx-web`) is the fast path for a code-only bad deploy — this already works correctly today: `.github/workflows/docker-publish.yml` tags every image with the immutable `${{ github.sha }}` in addition to `:latest`, and `infrastructure/ci-cd/deploy.sh` deploys by that SHA, so `kubectl`'s rollout history already has the real previous image, not `:latest`
- [ ] Before rolling back a deploy that shipped an Alembic migration, the migration has been read and classified (purely additive vs. destructive/renaming) — do not default to `alembic downgrade` without that read; see the runbook's Step 3b decision tree

## Disaster Recovery / Backup & Restore

Full procedure: `docs/operations/disaster-recovery-runbook.md`.

- [ ] Daily automated backup (`modules/backups/tasks.py`) confirmed actually running — check for a recent `COMPLETED` `BackupJob` via `GET /api/v1/backups`, not just that the Celery beat schedule exists
- [ ] A restore has actually been performed against a disposable/drill database at least once — `apps/api/scripts/restore_backup.py` is validated by its own test suite (`tests/integration/test_restore_backup_integration.py`), but a real restore drill against production-shaped data volume is what actually establishes your RTO figure, not an assumption
- [ ] Whoever is on-call has the `--database-url` credentials and object-storage access needed to run `restore_backup.py` *before* an incident, not discovered for the first time during one
- [ ] If relying on this platform's own backups as the primary DR mechanism (i.e. the self-hosted/Compose path, not AWS RDS's own automated backups) — confirmed, not assumed, since `infrastructure/terraform/database.tf`'s RDS backups are a separate, faster path for the AWS-hosted deployment

## Observability

- [ ] `/metrics` (Prometheus) scraped — see `infrastructure/monitoring/prometheus.yml`
- [ ] Alert rules loaded (`infrastructure/monitoring/alert_rules.yml`) and routed to a real on-call channel via Alertmanager (not included — deployment-specific)
- [ ] Structured logs (`app/core/logging_config.py`) shipped somewhere queryable — implemented via Fluent Bit + Grafana Loki (`infrastructure/monitoring/README.md`, `docs/logging-architecture-proposal.md`); apply `loki-bucket-init-job.yaml` → `loki-deployment.yaml` → `fluent-bit-daemonset.yaml` in that order. Every request already carries an `X-Request-ID`/`request_id` for cross-referencing, plus `organization_id`/`user_id` where the request resolves them
- [ ] Loki retention period intentionally set for this deployment (default: 720h/30 days, `infrastructure/monitoring/loki/loki-config.yaml`'s `limits_config.retention_period`) — not left at any tool default
- [ ] `erpx-logs` MinIO/S3 bucket encryption/versioning confirmed, matching the existing `erpx-storage` bucket's policy (same item above, one row up)
- [ ] LogQL query path (`/loki/api/v1/query_range`, and a live Grafana Explore query) validated against the real, running Loki instance before relying on it during an incident — a query-path anomaly was encountered against a short-lived validation instance during implementation and could not be conclusively root-caused; see `docs/operations/logging-runbook.md`'s "Loki is up and receiving data, but LogQL queries return nothing" section
- [ ] `/api/v1/health/ready` wired as the Kubernetes readinessProbe, `/api/v1/health` as the liveness probe (lightweight, no dependency calls) — see `infrastructure/kubernetes/api-deployment.yaml` for why these are deliberately different endpoints. Readiness checks Postgres, Redis, MinIO, and Elasticsearch, but only Postgres is classified `critical` (gates the 200/503 outcome) — see `docs/architecture/health-checks.md` for the full dependency classification and why (a prior version failed readiness on Elasticsearch alone, which would have kept every pod out of rotation in any environment without it, i.e. all of them at time of writing)

## Security

- [ ] Rate limiting (`slowapi`, `RATE_LIMIT_DEFAULT`) tuned for real traffic — the 100/minute default is a starting point, not a production-tuned value
- [x] Dependency vulnerability scanning on `apps/api/requirements.txt` and all 4 frontend apps' `package.json` — `pip-audit` (backend) + `npm audit` (frontend, all 4 apps in the existing CI matrix) added to `.github/workflows/ci.yml`, gated to fail the build only on Critical/High severity (Low/Moderate reported, non-blocking) via `.github/scripts/pip_audit_severity_gate.py` (backend) and npm's native `--audit-level=high` (frontend). **This surfaced real, pre-existing Critical/High vulnerabilities that were never caught before** — see finding #15 in `docs/project-hardening-audit.md`; resolving them (dependency upgrades) is separate, deliberately out-of-scope follow-up work, not done as part of adding the scanner itself
- [ ] Container image scanning enabled on push (ECR's `scan_on_push` is on by default in `infrastructure/terraform/storage.tf`)
- [ ] Secrets never in environment variable dumps/logs — verify `app/core/logging_config.py` doesn't log full request bodies for `/auth/*` endpoints
- [ ] `docs/security/` reviewed for anything specific to modules handling especially sensitive data (Payroll, Pentrix VAPT findings, Corporate SOC incidents)

## Performance

- [ ] `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` (see `app/db/session.py`) sized for expected concurrent request volume — the defaults (20/10) suit a single API replica; multiply pool headroom by replica count against your Postgres `max_connections`
- [ ] GZip compression is on for responses > 1KB (`app/main.py`) — no action needed, just confirming it's there
- [ ] Reports that scan large tables in Python (`modules/reports/registry.py`'s CRM pipeline / HR attendance dispatchers fetch up to 10,000 rows and aggregate in-process) — fine at current scale; revisit with a `GROUP BY` query if any tenant's row counts grow far beyond that
- [ ] HorizontalPodAutoscaler thresholds (`infrastructure/kubernetes/api-deployment.yaml`) validated against real load-test numbers, not left at the 70%/80% CPU/memory defaults untested
