# ERPX v1.0.0 — Deployment Instructions

Two supported paths: **Docker Compose** (single-host / staging) and
**Kubernetes** (production). The API image is self-contained as of `925bfa0`
(built from the repository-root context) — no host bind-mounts are required in
production.

Prerequisites: a provisioned PostgreSQL 16, Redis, and MinIO (or S3-compatible)
reachable by the app; secrets prepared (see below); `docs/deployment/production-checklist.md`
completed.

---

## 0. Required environment / secrets

Provide via environment (Compose `env` / K8s `Secret erpx-secrets`). Minimum:

| Key | Notes |
|---|---|
| `DATABASE_URL` | e.g. `postgresql+asyncpg://erpx:<pw>@<host>:5432/erpx` |
| `REDIS_URL` | Celery broker + rate-limit + cache store |
| `JWT_SECRET_KEY` | **≥ 32 chars, not a placeholder** — the app refuses to start otherwise |
| `ENVIRONMENT` | `production` |
| `MINIO_*` / storage creds | object storage |
| `CACHE_ENABLED`, `OTEL_*`, `SENTRY_*` | optional; disabled by default |

Never bake secrets into the image; the repo-root `.dockerignore` excludes `.env`.

---

## 1. Build & publish the image (CI-preferred)

CI (`.github/workflows/docker-publish.yml`) builds from the repo root with
`file: apps/api/Dockerfile` and pushes `ghcr.io/gir-technologies/erpx-api:latest`
and `:<git-sha>` after CI passes. To build manually:

```bash
# From the repository root:
docker build -f apps/api/Dockerfile -t ghcr.io/gir-technologies/erpx-api:1.0.0 .
docker push ghcr.io/gir-technologies/erpx-api:1.0.0
```

Sanity-check the image is self-contained **before** deploying:

```bash
docker run --rm --entrypoint python ghcr.io/gir-technologies/erpx-api:1.0.0 \
  -c "import app.main; print('image OK')"
```

---

## 2. Apply database migrations (always before rolling out new code)

Migrations are forward-only in normal operation and fully reversible for
rollback (38 revisions, head `0038`).

```bash
# Run against the target DB with DATABASE_URL set. From apps/api:
alembic upgrade head
alembic current   # must report 0038 (head)
```

In Kubernetes, run this as a one-shot Job (or init container) with the same image
and `erpx-secrets`, gated before the Deployment rollout.

---

## 3a. Deploy — Docker Compose (staging / single host)

```bash
# From the repository root:
docker compose up -d postgres redis minio
docker compose run --rm api alembic upgrade head     # migrate first
docker compose up -d api celery_worker celery_beat web nginx
docker compose ps                                     # all healthy
```

---

## 3b. Deploy — Kubernetes (production)

```bash
kubectl apply -f infrastructure/kubernetes/          # or your kustomize/helm wrapper
kubectl -n <ns> set image deployment/erpx-api \
  erpx-api=ghcr.io/gir-technologies/erpx-api:1.0.0
kubectl -n <ns> rollout status deployment/erpx-api --timeout=180s
```

The Deployment defines **readiness**, **liveness**, and **startup** probes against
`/api/v1/health*`, resource requests/limits, HPA, and pulls secrets from
`erpx-secrets`. The readiness probe fails only on *critical* dependencies
(database/redis/storage) — Elasticsearch (`search`) is intentionally
non-critical.

---

## 4. Post-deploy

Run the smoke test (`docs/release/SMOKE_TEST.md`). Confirm dashboards
(Grafana/Prometheus) and traces/logs are flowing. If anything fails, follow
`docs/release/ROLLBACK_PLAN.md`.
