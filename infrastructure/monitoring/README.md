# ERPX Monitoring & Log Shipping

Two related but independent stacks, both opt-in via
`docker compose --profile monitoring up` (or, on Kubernetes, applied
separately from the core application manifests):

- **Metrics**: Prometheus + Grafana + exporters (`prometheus.yml`,
  `alert_rules.yml`, `grafana/`) — pre-existing, unchanged by this work.
- **Logs**: Fluent Bit + Grafana Loki (`fluent-bit/`, `loki/`,
  `grafana/datasources/loki.yml`, `grafana/dashboards/erpx-logs-overview.json`)
  — implements the architecture approved in
  `docs/logging-architecture-proposal.md`.

## Log shipping — how it fits together

```
FastAPI / Celery worker / Celery beat / nginx (JSON stdout)
        │
        ▼
   Fluent Bit  (parse → mask sensitive fields → label)
        │  HTTP push
        ▼
     Loki  (index: labels only; chunks → MinIO/S3)
        │
        ▼
   Grafana  (Loki datasource + "ERPX Logs Overview" dashboard)
```

Every log line already carries `request_id`/`organization_id`/`user_id`
(see `docs/logging-architecture-proposal.md` Section 6) — Fluent Bit does
not need to add these, only `service`/`level` are promoted to Loki
*labels*; everything else stays in the log body, queried via LogQL line
filters (`| json | request_id="..."`), never as a label — see the
cardinality warning in `loki/loki-config.yaml`.

## Docker Compose

```bash
# 1. One-time: create the erpx-logs MinIO bucket, start Loki + Fluent Bit
docker compose --profile monitoring up -d loki-bucket-init loki fluent-bit prometheus grafana

# 2. Wire the four traffic-generating services (api, celery_worker,
#    celery_beat, nginx) to actually ship their logs — see
#    docker-compose.monitoring.yml's own header comment for exactly why
#    this is a separate override file rather than baked into the base
#    docker-compose.yml.
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml \
  --profile monitoring up -d
```

Grafana: http://localhost:3001 (`admin` / `${GRAFANA_ADMIN_PASSWORD:-change_me}`)
→ Explore → Loki datasource, or the "ERPX Logs Overview" dashboard.

**Known limitation:** once `docker-compose.monitoring.yml` is applied,
`docker compose logs api` (and `celery_worker`/`celery_beat`/`nginx`) stop
working via the Docker CLI for those four services specifically — the
`fluentd` logging driver fully replaces `json-file`, and `docker logs`
only supports `json-file`/`local`/`journald`. This is a standard,
well-documented tradeoff of centralized log shipping via Docker's own
logging drivers, not a bug — use Grafana/Loki to read those services'
logs once the override file is applied, or drop
`docker-compose.monitoring.yml` from the command to get `docker compose logs`
back (log shipping stops too — it's the same on/off switch).

**Also note:** JSON logs only ship in `ENVIRONMENT=production` — dev mode's
human-readable console output isn't JSON by design (see
`apps/api/app/core/logging_config.py`), so Fluent Bit's parser filter
leaves it unparsed (`Reserve_Data On`) rather than dropping it. To
exercise the full pipeline locally, run with `ENVIRONMENT=production` set.

## Kubernetes

```bash
kubectl apply -f infrastructure/kubernetes/loki-bucket-init-job.yaml
kubectl wait --for=condition=complete job/erpx-loki-bucket-init -n erpx --timeout=60s
kubectl apply -f infrastructure/kubernetes/loki-deployment.yaml
kubectl apply -f infrastructure/kubernetes/fluent-bit-daemonset.yaml
```

`fluent-bit-daemonset.yaml` includes its own ServiceAccount/ClusterRole/
ClusterRoleBinding (read-only: `get`/`list`/`watch` on pods/namespaces,
for the `kubernetes` filter's metadata enrichment — nothing else).

## Validation performed during implementation

Real, empirical checks — not just config review:

- `docker compose config` (base file, and merged with the override file)
  — both validate cleanly; confirmed via inspection that the `fluentd`
  logging driver is genuinely absent from every service unless both
  compose files are combined.
- `fluent-bit --dry-run` against both the Compose config and the
  Kubernetes ConfigMap's embedded config (including the `kubernetes`
  filter) — both pass syntax validation.
- `loki -verify-config` against both the Compose config and the
  Kubernetes ConfigMap's embedded config, with real MinIO env vars
  expanded — both pass.
- A real Fluent Bit + Loki pair, run standalone against the project's
  actual standalone MinIO instance: confirmed the `erpx-logs` bucket gets
  created (`loki-bucket-init`'s exact `mc` command), Fluent Bit accepts
  forward-protocol records and reports `0 errors` through its full filter
  chain (parse → Lua mask → record_modifier → Loki output), and Loki's
  own metrics confirm real ingestion (`loki_distributor_lines_received_total`,
  `loki_ingester_memory_streams`) with the exact expected label set
  (`{service="erpx-api", level="info", job="erpx", deployment="compose"}`,
  confirmed via Loki's `/loki/api/v1/series` endpoint).
- **Known gap, disclosed rather than hidden:** LogQL read queries
  (`/loki/api/v1/query`) against that same standalone Loki instance
  returned empty results despite the data being confirmed present in the
  ingester's memory (`loki_ingester_memory_chunks=1`) — reproduced
  identically with plain filesystem storage (MinIO/S3 entirely removed
  from the equation) and across both schema v11 and v12, isolating the
  cause to something about running Loki as a single, freshly-booted,
  short-lived container rather than to this repository's actual
  `loki-config.yaml`/`fluent-bit.conf` content. Re-validate the query path
  (`/loki/api/v1/query_range`, and a live Grafana Explore query) against a
  longer-running deployment before relying on this in an incident —
  tracked as a follow-up in `docs/operations/logging-runbook.md`.
