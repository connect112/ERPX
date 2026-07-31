# ERPX v1.0.0 — Post-Deploy Smoke Test Checklist

Run immediately after every deploy/rollback, against the target environment.
`BASE=https://<api-host>`. Stop and roll back on any ❌.

## A. Image / process health
- [ ] Image self-contained: `docker run --rm --entrypoint python <image> -c "import app.main; print('ok')"` prints `ok` (no `ModuleNotFoundError`).
- [ ] Pods/containers report **healthy** (`kubectl get pods` / `docker compose ps`); no crash-loops.

## B. Health & readiness endpoints
- [ ] `curl -fsS $BASE/api/v1/health` → 200.
- [ ] `curl -fsS $BASE/api/v1/health/ready` → 200 and `ready: true` (critical deps: database, redis, storage healthy).
- [ ] `curl -fsS $BASE/metrics` → Prometheus exposition (200).

## C. Database & migrations
- [ ] `alembic current` reports the expected head (`0038` for 1.0.0).
- [ ] A trivial read endpoint returns data (no DB connection errors in logs).

## D. AuthN / AuthZ (core security path)
- [ ] `POST $BASE/api/v1/auth/login` with valid creds → 200 + access token.
- [ ] Authenticated `GET` (e.g. dashboard summary) with the token → 200.
- [ ] Same request **without** a token → 401.
- [ ] A Staff-tier token hitting an admin-only route → 403 (RBAC enforced).
- [ ] Rapid repeated `POST /auth/login` (>10/min from one IP) → eventually 429 (rate limiting active).

## E. Write path & data integrity
- [ ] Create one record (e.g. a lead or an inventory item) → 201; read it back.
- [ ] Post a balanced journal entry → 201; an unbalanced one → 400 (double-entry enforced).
- [ ] Confirm the write is visible after a fresh request (persistence, not just cache).

## F. Async / jobs / storage
- [ ] Celery worker + beat are up and consuming (logs show task pickup; no broker errors).
- [ ] Request a document upload URL (presigned) → 200 with a URL (MinIO/S3 reachable).

## G. Observability
- [ ] Structured logs are flowing with `request_id` (and `trace_id`/`span_id` if OTel enabled).
- [ ] Grafana/Prometheus dashboards show live API metrics; Sentry receiving events (if enabled).

## H. Frontend
- [ ] Web app loads over HTTPS; login flow succeeds; an authenticated page renders.
- [ ] Network tab shows the SPA calling the correct API base and receiving 200s.
- [ ] No console errors on first paint; lazy-loaded route chunks load on navigation.

## Sign-off
- [ ] All checks ✅ → release confirmed live.
- [ ] Any ❌ → execute `docs/release/ROLLBACK_PLAN.md`, record the failure, do not proceed.

Operator: __________________  Date/Time: __________  Env: __________  Result: PASS / FAIL
