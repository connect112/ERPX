# Logging Operations Runbook

Covers the Fluent Bit + Grafana Loki log shipping pipeline implemented per
`docs/logging-architecture-proposal.md`. For the application-side logging
schema itself (fields, correlation, JSON conventions), see that
document's Section 6 — this runbook is about the shipping pipeline
specifically: how to query it, how to tell if it's broken, and how to fix
the common failure modes.

## Querying logs

**By request_id** (the most common investigation): every API/Celery/nginx
log line for a single request shares the same `request_id` — the API's
own `X-Request-ID` response header, and (for authenticated requests) the
same value as the matching `AuditLog.request_id` row.

In Grafana → the "ERPX Logs Overview" dashboard, paste the `request_id`
into the "Filter by request_id" box at the top. Or directly in Explore:

```logql
{job="erpx"} | json | request_id="req-abc-123"
```

**By organization** (only populated for requests whose dependency chain
resolves one — see `docs/logging-architecture-proposal.md` Section 6,
"mirrors `AuditLog.organization_id`'s existing nullability"):

```logql
{job="erpx"} | json | organization_id="org-uuid-here"
```

**Errors only, across every service, last hour:**

```logql
{job="erpx", level="error"}
```

**A specific pod's logs after it's already been deleted** (the entire
point of this pipeline — container stdout is gone once the pod is,
kubelet log rotation notwithstanding):

```logql
{job="erpx", deployment="kubernetes"} | json | kubernetes_pod_name="erpx-api-abc123"
```

## Health checks

- **Loki**: `GET http://loki:3100/ready` (K8s: `kubectl exec` into any pod
  with network access, or `kubectl port-forward svc/loki 3100:3100`).
  `200 ready` = healthy. Also exposes `/metrics` (scraped by Prometheus,
  see `infrastructure/monitoring/prometheus.yml`'s `loki` job) —
  `LokiDown` fires in Alertmanager if that scrape target goes down for 2m+
  (`infrastructure/monitoring/alert_rules.yml`).
- **Fluent Bit**: `GET http://fluent-bit:2020/api/v1/health` — `200 OK` =
  healthy. `GET http://fluent-bit:2020/api/v1/metrics` gives per-plugin
  record counts and error counts (input/filter/output) — the fastest way
  to see exactly where the pipeline is dropping records if something's
  wrong (compare `input.forward.0.records` against `output.loki.0.proc_records`;
  a growing gap means records are being dropped somewhere in the filter
  chain, check `output.loki.0.errors`/`retries_failed` for push failures
  specifically). `FluentBitDown` fires the same way as `LokiDown`.

## Common failure modes

**Fluent Bit is up, but nothing appears in Loki:**
1. Check `output.loki.0.errors` via Fluent Bit's `/api/v1/metrics` — a
   nonzero value means Loki rejected the push (check Fluent Bit's own
   stderr/logs for the HTTP status Loki returned).
2. Confirm Loki's `/ready` actually returns `ready`, not a 503.
3. Compose path only: confirm `docker-compose.monitoring.yml` was
   included in the `up` command — without it, the four traffic-generating
   services still use the default `json-file` driver and never reach
   Fluent Bit's forward input at all (see
   `infrastructure/monitoring/README.md`'s "Known limitation").

**Loki is up and receiving data, but LogQL queries return nothing:**
This exact symptom was encountered during implementation against a
freshly-started, single-container Loki instance — data was confirmed
present via `loki_ingester_memory_streams`/`loki_ingester_memory_chunks`
metrics and the `/loki/api/v1/series` endpoint, but `/loki/api/v1/query`
returned an empty result set. Reproduced identically with plain
filesystem storage (ruling out the MinIO/S3 integration as the cause) and
across schema v11/v12. Root cause was not conclusively identified within
that investigation — suspected to be a Loki 2.9.x monolithic-mode
querier/ingester ring-bootstrap race specific to a very-short-lived
single instance, not a defect in this repository's `loki-config.yaml`. If
this recurs against a real, longer-running deployment:
1. Confirm via `/loki/api/v1/series?match[]={job="erpx"}` and the
   `loki_ingester_memory_streams` metric that the ring genuinely holds
   the expected stream (rules out "nothing was ingested").
2. Try `POST /flush` to force an immediate chunk flush to object storage,
   then retry the query via the store path rather than the ingester path.
3. Check Loki's own logs for `XMinioInvalidObjectName` or similar S3
   errors during flush — this exact implementation hit and fixed one
   (schema `v12`'s chunk key format was rejected by MinIO; fixed by using
   schema `v11`, see `loki-config.yaml`'s own comment). A different S3
   error here would point at a MinIO/bucket-permissions problem instead.
4. If the query path still returns nothing against a real deployment
   after a full restart, file this as a genuine bug against this
   implementation, not an environment artifact — the ad hoc validation
   during implementation could not rule that out with certainty; see
   `infrastructure/monitoring/README.md`'s "Known gap" note.

**`erpx-logs` bucket doesn't exist / Loki fails to start with an S3
error:** run the bucket-init step manually — Compose:
`docker compose --profile monitoring up loki-bucket-init`; Kubernetes:
`kubectl apply -f infrastructure/kubernetes/loki-bucket-init-job.yaml`.

**Sensitive data appears in a log line despite the masking filter:** the
Lua filter (`infrastructure/monitoring/fluent-bit/mask_sensitive_fields.lua`)
only redacts values under a fixed list of known key *names* (`password`,
`token`, `secret`, etc.) — it cannot catch a secret embedded in free text
under an unexpected key. Fix the logging call site (the real, primary
defense — see `docs/deployment/production-checklist.md`'s "Secrets never
in environment variable dumps/logs" item), then add the missing key name
to `SENSITIVE_KEYS` in the Lua script (both copies — Compose's file and
the Kubernetes ConfigMap's embedded copy, see that script's own comment
for why there are two) as a second, pipeline-level layer against the same
mistake recurring.

## Retention / storage growth

Loki's compactor deletes data older than `limits_config.retention_period`
(currently 720h / 30 days) automatically — no manual intervention needed
under normal operation. If the `erpx-logs` MinIO/S3 bucket grows faster
than expected:
1. Confirm the retention period is actually what you expect:
   `grep retention_period infrastructure/monitoring/loki/loki-config.yaml`.
2. Check `loki_compactor_...` metrics (scraped by Prometheus) for
   compaction run frequency/failures.
3. As a last resort, MinIO's own `mc` CLI can list/delete objects
   directly in the `erpx-logs` bucket — but prefer letting the compactor
   catch up over manual deletion, which can leave the boltdb-shipper
   index referencing chunks that no longer exist.
