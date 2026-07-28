# Health, Readiness & Liveness

Implementation: `apps/api/app/api/v1/health.py`
Consumed by: `infrastructure/kubernetes/api-deployment.yaml` (readiness/liveness/startup probes), `apps/api/Dockerfile` (`HEALTHCHECK`), Playwright's `apps/web/e2e/global-setup.ts`, and the Locust load test.

## Two endpoints, two very different jobs

| Endpoint | Purpose | Checks dependencies? | Used by |
|---|---|---|---|
| `GET /api/v1/health` | Liveness — "is the process up at all" | No | Docker `HEALTHCHECK`, K8s `livenessProbe` + `startupProbe`, e2e/load-test bootstrap |
| `GET /api/v1/health/ready` | Readiness — "can this pod usefully serve traffic right now" | Yes | K8s `readinessProbe` |

These are deliberately different endpoints with different failure semantics.
Liveness answering `200` even while a downstream dependency is unhealthy is
correct, not a bug: if Postgres is briefly slow, Kubernetes should *not*
conclude the API process itself is broken and kill/restart otherwise-healthy
pods over it. Only readiness — which controls whether the Service routes
traffic to a pod, not whether the pod lives or dies — should react to
dependency health.

## Readiness policy: critical vs. optional dependencies

`/health/ready` checks four dependencies (`database`, `redis`, `storage`,
`search`) every time it's called, and always reports all four in the response
body — but **only a `critical` dependency failing causes the endpoint to
return 503**. This is the fix for a production-readiness audit finding: the
original implementation treated all four as equally required, which meant a
Kubernetes deployment with no Elasticsearch running (true of every
environment as of this writing — nothing in the codebase queries it) would
have every pod permanently fail readiness and receive zero traffic, even
though the platform is otherwise fully functional.

| Dependency | Classification | Why |
|---|---|---|
| `database` (PostgreSQL) | **Critical** | Auth, RBAC, and virtually every endpoint reads or writes it. Nothing works without it. |
| `redis` | Optional | Celery broker only. Two request-time paths use it directly (`modules/authentication/service.py`'s `.delay()` calls for verification/reset emails — see note below), plus scheduled/background jobs, but no other endpoint's request/response cycle touches it. `modules/backups/service.py` already documents that Redis "isn't guaranteed to be reachable in every deployment of this codebase." |
| `storage` (MinIO) | Optional | Only document/media upload-download and backup-download features use it; the rest of the platform doesn't touch object storage. |
| `search` (Elasticsearch) | Optional | Nothing in the codebase queries it — `packages/search/` is empty. There is no feature to break. |

**Known related gap, intentionally not fixed here** (out of scope — this
change is readiness-policy only, not a business-logic fix): the two
`.delay()` calls in `modules/authentication/service.py` (registration and
password-reset emails) are not wrapped in error handling, so if Redis is
genuinely unreachable, those two specific endpoints will 500 rather than
degrading gracefully. Classifying `redis` as optional for *readiness* is
still correct — losing 2 of 100+ endpoints doesn't justify pulling every pod
out of the load balancer — but it does mean the fix for those 2 endpoints
specifically is separate follow-up work (wrap the `.delay()` calls, catch the
broker connection error, log and continue rather than raise).

## Response shape

```json
GET /api/v1/health/ready

// 200 when the critical dependency is healthy, regardless of optional ones
{
  "status": "ready",
  "ready": true,
  "live": true,
  "checks": {
    "database": { "healthy": true, "critical": true },
    "redis":    { "healthy": true, "critical": false },
    "storage":  { "healthy": true, "critical": false },
    "search":   { "healthy": false, "critical": false }
  }
}

// 503 only when a critical dependency is unhealthy
{
  "status": "not_ready",
  "ready": false,
  "live": true,
  "checks": {
    "database": { "healthy": false, "critical": true },
    ...
  }
}
```

Nothing in the codebase currently parses this body programmatically (K8s's
`httpGet` readiness probe only inspects the HTTP status code) — the JSON
shape can evolve without a compatibility concern, but is kept stable and
documented here for operator dashboards and manual debugging.

## Adding a new dependency check

1. Add a `check_<name>() -> bool` async function in `health.py`, following
   the existing pattern (try the real client call, `except Exception: return
   False`).
2. Add it to `DEPENDENCY_CHECKS` with its criticality, using the function's
   **name as a string**, not a direct reference: `"check_fn_name", is_critical`.
   `readiness()` resolves it via `globals()[checker_name]` at call time
   rather than storing the function object — this is what lets tests
   `monkeypatch.setattr(health_module, "check_fn_name", fake)` and have
   `readiness()` actually pick up the replacement. A dict of direct function
   references would freeze in the original function at import time and
   silently ignore any later monkeypatch (this was a real bug caught while
   writing `tests/api/test_health.py` for this change — several tests
   silently fell through to real network calls instead of the fakes until
   this was fixed).
3. If `is_critical=True`, make sure that's actually true — ask "would most
   requests genuinely fail without this," not "is this dependency
   important." Getting this wrong in either direction either masks a real
   outage (too lenient) or takes healthy pods out of rotation over a
   non-essential integration (too strict — this was exactly the
   Elasticsearch bug this document exists to explain).
4. Add the corresponding test cases to `tests/api/test_health.py` (healthy,
   unhealthy-but-optional or unhealthy-critical as appropriate, and confirm
   it doesn't change the outcome of the "all optional dependencies down"
   test if optional).

## Separate from the in-app Monitoring module

`modules/monitoring/` (RBAC-gated, `GET /api/v1/monitoring/health`) is a
different, independently-implemented feature: an in-app dashboard for
administrators, with its own direct checks (real `SELECT 1`, real MinIO
`ensure_bucket()`, real Redis `PING`) and its own three-way `healthy` /
`degraded` / `unhealthy` status model. It does not call and is not called by
`/health/ready` — the two serve different audiences (Kubernetes vs. a
logged-in administrator) and were deliberately kept separate rather than
merged, so a change to one's policy doesn't silently change the other's.
