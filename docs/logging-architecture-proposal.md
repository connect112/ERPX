# ERPX Log Shipping — Architecture Design Proposal (v2)

Status: **architecture approved.** The Fluent Bit + Grafana Loki shipping
pipeline itself (Section 4) is **not yet implemented** — no Loki/Fluent Bit
code, manifests, or config exist yet; still waiting for explicit approval to
start that work. The **prerequisites** this proposal's Risk Assessment
(Section 5, both High-severity rows) called out as required *before* shipping
— structured JSON logging on every entrypoint including Celery, and
`organization_id` correlation — have been implemented and tested; see
Section 6. Addresses Production Hardening Audit finding #6
(`docs/project-hardening-audit.md`).

This supersedes the v1 proposal written for the same finding — extended in
place, not duplicated, to the more exhaustive specification requested.
Every claim below is grounded in a specific file path or an empirical test
run against this codebase, not assumed.

---

## 1. Baseline Verification & Current State Analysis

### App / API

- **Generation:** `structlog` (`apps/api/app/core/logging_config.py`), one
  process-wide configuration via `configure_logging()`, called from
  `apps/api/app/main.py`'s module scope.
- **Data flow:** every module obtains a logger via `get_logger(__name__)`
  and calls it directly at the point of the event (e.g.
  `modules/authentication/service.py:65`, `logger.info("user_registered", ...)`)
  — no intermediate queue or buffering layer; log calls are synchronous
  writes to stdout.
- **Storage:** `logging.basicConfig(stream=sys.stdout, ...)`. No file, no
  external sink. Verified empirically (ran against this exact codebase):
  ```
  ENVIRONMENT=production, real secret set:
  {"foo": "bar", "event": "test_log_line", "level": "info", "timestamp": "2026-07-28T10:05:38.451309Z"}
  ```
- **Retention:** None — governed entirely by whatever the container
  runtime's stdout capture does (node-local `json-file` driver in Docker,
  kubelet-rotated in K8s), not by anything this codebase controls.
- **Limitations:** No shipping, no durable retention, no external
  queryability once a pod/container is gone.
- **Security posture:** No log line is currently encrypted at rest (inherits
  whatever the node's local disk encryption is, outside this codebase's
  control) or access-controlled (`docker logs` / `kubectl logs` access is
  gated only by whatever cluster/host-level RBAC exists, not by anything
  ERPX defines).
- **Missing capabilities:** durability, external queryability, retention
  policy, access control scoped to ERPX's own RBAC model.

### Celery (worker / beat)

- **Generation:** Same `structlog` `get_logger()` calls, from the same task
  modules (`modules/backups/tasks.py`, `modules/accounting/invoices/tasks.py`,
  `modules/reports/tasks.py`, `modules/crm/followups/tasks.py`).
- **Critical finding, verified empirically:** `configure_logging()` is
  called **only** from `apps/api/app/main.py`. `infrastructure/kubernetes/
  celery-deployment.yaml`'s worker command
  (`celery -A app.core.celery_app worker --loglevel=info --concurrency=4`)
  and the beat deployment's equivalent import **only** `app.core.celery_app`
  — never `app.main`. Running exactly that import path and logging through
  the same `get_logger()` API produces:
  ```
  2026-07-28 15:11:53 [info     ] test_log_line                  foo=bar
  ```
  — structlog's un-configured default renderer: plain key=value text, no
  `timestamp` field, no JSON structure. **API logs and Celery logs are
  today in two different formats**, despite using the identical logging
  API at the call site.
- **Data flow / Storage / Retention:** Same stdout-only, no-shipping,
  node-governed-retention story as API logs.
- **Limitations:** The format inconsistency above means any future JSON-only
  log pipeline will silently fail to structure every Celery log line until
  this is fixed.
- **Security posture:** Same as API (no encryption/access-control layer
  this codebase defines).
- **Missing capabilities:** Same as API, plus the format-consistency fix
  itself.

### Nginx (docker-compose path) vs. Ingress (Kubernetes path) — these are two different components, not one

- **Docker Compose:** `infrastructure/nginx/nginx.conf` — verified by
  direct read: **zero** `access_log`, `error_log`, or `log_format`
  directives anywhere in the file. Nginx therefore runs on its
  compile-time defaults (typically `combined` format to
  `/var/log/nginx/{access,error}.log`). The official `nginx:alpine` image
  (`docker-compose.yml` line 208) conventionally symlinks those paths to
  stdout/stderr, but that is an image-level default this repository's own
  config does not pin or document — a real ambiguity, not a verified fact.
  Nginx's default access log format does **not** include the app's
  `X-Request-ID` — no `log_format` directive was defined to add it — so
  nginx access logs today **cannot be correlated** with API/Celery logs at
  all via any shared identifier.
- **Kubernetes:** No nginx container exists in this path.
  `infrastructure/kubernetes/ingress.yaml` uses `ingressClassName: nginx`
  with `nginx.ingress.kubernetes.io/*` annotations — this is the
  **ingress-nginx controller**, an external, cluster-level add-on the
  manifest's own comment says is a prerequisite ("Requires an ingress-nginx
  controller... already installed on the cluster"), not something deployed
  by this repository. Its logs live entirely outside this codebase's
  control or knowledge — a genuinely different log source than the
  Compose path's nginx container, with different (and here, unverified)
  format/retention characteristics depending on how that cluster-level
  add-on happens to be configured.
- **Missing capabilities:** request-ID correlation (Compose path), any
  visibility into ingress-nginx's actual logging config (K8s path, out of
  this repo's scope by design).

### Kubernetes / Docker container logs (general)

- Already covered under App/API and Celery above — no separate collection
  mechanism exists beyond the container runtime default. Confirmed by grep:
  zero DaemonSet, sidecar, or `fluent-bit`/`fluentd`/`filebeat` reference
  anywhere in `infrastructure/kubernetes/`. Zero `logging:` driver override
  in `docker-compose.yml` (only match for `driver:` in the whole file is
  the `bridge` network driver).

### Audit

- **Generation:** Fully automatic — `modules/audit/hooks.py`'s SQLAlchemy
  `before_flush`/`after_flush` session event listeners, registered once at
  app startup (`register_audit_hooks()`, called from `apps/api/app/main.py`).
  Fires for every `session.new`/`session.dirty`/`session.deleted` object
  across every module, with no per-module code required.
- **Data flow:** In-process SQLAlchemy events → `AuditLog` ORM object →
  written to Postgres in the **same transaction** as the change it
  describes (added inside `after_flush`, which SQLAlchemy folds into the
  active flush) — an audit entry can never exist without, or disagree
  with, the change it records.
- **Storage:** Real Postgres table (`audit_logs`), `JSONB` diff column
  (`AuditLog.changes`).
- **Retention:** Indefinite — no deletion path exists in the codebase.
  Durability comes from RDS's 14-day automated backup retention
  (`infrastructure/terraform/database.tf`), independent of anything in
  this proposal.
- **Limitations:** Captures data *mutations* only — not requests that
  didn't change data, not errors, not performance/timing information.
- **Security posture:** RBAC-gated read access via `modules/audit/routes.py`;
  append-only by design (`AuditLog` has no `updated_at` — the model's own
  docstring states this is deliberate).
- **Missing capabilities:** Nothing, for its actual purpose — this system
  is complete and does not need "log shipping."

### Security / Auth

- **Generation:** Not a distinct subsystem — security-relevant events
  (`modules/authentication/service.py`) log through the exact same
  `structlog` calls as everything else: `login_failed_bad_password`,
  `login_success`, `password_reset`, `password_changed`,
  `two_factor_enabled`, `two_factor_disabled` (confirmed by direct grep —
  6 distinct security-relevant event names, all `logger.info`/`logger.warning`).
- **Data flow / Storage / Retention:** Identical to general App/API logs —
  same stdout sink, same lack of durability. A failed-login-attempt log
  line has exactly the same (lack of) retention guarantee as a routine
  request-completed line today.
- **Limitations:** No dedicated security-event stream, no anomaly
  detection, no SIEM-style correlation across events (e.g., N failed
  logins from one IP within M minutes) — the application-level compensating
  control that exists for this specific case is account lockout
  (`modules/authentication/repository.py`'s `register_failed_login`, a
  real, already-implemented database-backed mechanism — the *log line* is
  incidental to that control, not load-bearing for it).
- **Security posture:** Same as general app logs — no additional
  protection today despite the higher sensitivity of this event category.
- **Missing capabilities:** durability specifically matters more here than
  for routine logs — losing a `login_failed_bad_password` trail on pod
  restart removes exactly the evidence an incident investigation would
  need most.

### Error

- **Generation:** `apps/api/app/core/exception_handlers.py`'s
  `unhandled_exception_handler` calls `logger.exception(...)` (captures
  full traceback) for any exception not otherwise handled; `ERPXException`
  subclasses log via `logger.warning` in `erpx_exception_handler`.
- **Data flow:** Same synchronous stdout write as every other log call.
  The client-facing response never includes the traceback — only
  `request_id`, matching the consistent error envelope
  (`_envelope()` in the same file) — the traceback exists **only** in the
  server-side log line, making its durability the sole way to actually
  debug a production 500 after the fact.
- **Storage / Retention:** Same as general logs — this is the single
  highest-value case for the "logs lost on pod eviction" problem finding
  #6 names, since it is often the *only* record of what actually happened.
- **Security posture:** Same as general logs.
- **Missing capabilities:** durability (as above), and no error
  aggregation/deduplication (e.g., "this same exception has occurred 40
  times across 12 pods in the last hour") — that capability is
  specifically what an APM/error-tracking tool (Sentry, etc. — finding
  #10, not this proposal) would add; log shipping alone gives durable
  storage and search, not automatic grouping.

### Structured logging (cross-cutting)

- Already detailed above per-component. Summary: API logs are genuinely
  structured JSON in production; Celery logs are not (verified bug, see
  above); nginx/ingress logs are unstructured plain text with no
  ERPX-specific fields at all.

### Correlation / Request / Trace IDs

- **Request ID:** Real and working —
  `apps/api/app/middleware/request_context.py` assigns one per request
  (from `X-Request-ID` header or a fresh UUID), echoes it in the response
  header, includes it in every error envelope, and threads it into
  `AuditLog.request_id` via `app/core/audit_context.py`'s
  `set_audit_request_metadata()`. This is genuinely good, already-working
  cross-referencing between an access log line, any application log lines
  from that request, and any resulting audit trail row.
- **Trace ID:** **Does not exist.** No `opentelemetry` or `sentry_sdk` (or
  equivalent) package anywhere in `apps/api/requirements.txt` (confirmed
  by direct grep, matching the prior hardening audit's finding #10) —
  there is no span/trace concept in this codebase, only the single flat
  `request_id`. A request that fans out into multiple internal calls
  (e.g., an endpoint that calls another service, or a Celery task
  triggered mid-request) has no mechanism today to link those as one
  logical trace beyond manually passing `request_id` through, which is
  not currently done for Celery task dispatch (`modules/authentication/
  service.py`'s `.delay()` calls, for example, don't pass the calling
  request's `request_id` into the task's own log context).
- **Organization ID — a real, previously-unstated gap found while writing
  this section:** `app/core/audit_context.py` tracks `organization_id` in
  its own `ContextVar`, populated by `get_current_user_organization_id`,
  **specifically for `AuditLog` rows**. This is a *different* context-var
  mechanism than `structlog.contextvars`, which is what's actually merged
  into log output (`configure_logging()`'s `shared_processors` includes
  `structlog.contextvars.merge_contextvars`, but nothing in the codebase
  calls structlog's own `bind_contextvars(organization_id=...)`).
  **Consequence: application/API/Celery logs today can be correlated by
  `request_id` but cannot be filtered or scoped by `organization_id`** —
  on a platform that is multi-tenant at the row level, an operator cannot
  today answer "show me every log line touching Organization X" from logs
  alone; only the `AuditLog` table (which does carry `organization_id`)
  supports that query, and only for data *mutations*, not general request/
  error activity. This matters directly for Section 2's "Multi-tenancy"
  evaluation criterion and Section 4's data governance design.

---

## 2. Solutions Comparison Matrix

Evaluated against ERPX's verified stack: AWS (Terraform, `us-east-1`, zero
existing CloudWatch resources), Kubernetes + `ingress-nginx` (external
add-on) + Docker Compose (both real, supported deployment paths per
`docs/project-audit.md`), Prometheus + Grafana already deployed with a
provisioned datasource and dashboard (`infrastructure/monitoring/`), one
already-provisioned-but-unused, insecure-by-default Elasticsearch container
(`xpack.security.enabled=false`, `docker-compose.yml`), and the structured/
unstructured log-format split documented in Section 1.

### 1. Grafana Loki

- **Architecture:** Label-indexed log aggregator; raw content stored
  compressed in object storage (S3-compatible — MinIO already runs here),
  only metadata labels indexed.
- **Advantages:** Native Grafana datasource — the *same* already-deployed
  Grafana instance and dashboard gains logs with zero new UI; can use
  existing MinIO as its object store; LogQL shares PromQL's mental model,
  already familiar from the existing Prometheus setup.
- **Disadvantages:** Not full-text search across unindexed content; label
  cardinality discipline required (Loki's most common operational failure
  mode industry-wide).
- **Ops complexity:** Low-Medium — single Go binary, no cluster
  coordination needed at this scale.
- **Scalability:** Horizontally scalable if ever needed (microservices
  mode); monolithic mode comfortably fits ERPX's current pre-production
  scale.
- **Resource/Performance profile:** Low — no JVM, agents are lightweight.
- **K8s/Docker/Grafana/Prometheus integrations:** Excellent on all four —
  official Helm chart; official Docker image; native Grafana datasource
  (no plugin needed); Loki's ruler can alert through the same Alertmanager
  path Prometheus already uses (currently commented out, pending
  deployment, in `infrastructure/monitoring/prometheus.yml`).
- **Security/Compliance:** No built-in auth in OSS Loki — relies on
  Grafana's own access control (already exists) or a reverse proxy in
  front; no compliance certifications of its own (self-hosted OSS).
- **Multi-tenancy:** Loki has native multi-tenant mode (`X-Scope-OrgID`
  header) — could in principle map to ERPX's own organizations, but
  Section 1 already established that **no log line carries
  `organization_id` today**, so this capability has no data to act on
  without the separate context-var fix noted there; not a Loki limitation,
  an ERPX-application-layer prerequisite shared by every solution
  evaluated here.
- **HA/DR:** Stateless service (all state in object storage) — HA is
  running multiple replicas behind a load balancer; DR is "the object
  store's own durability," which for MinIO/S3 already has its own
  backup/versioning story independent of this proposal.
- **Cost:** Self-hosted, no SaaS fee; storage cost only (already paying
  for MinIO/S3 regardless of this decision).
- **Maintenance effort:** Low — no index/shard management.
- **Learning curve:** Low-Medium for anyone who already knows PromQL
  (already true for whoever manages the existing Prometheus setup); LogQL
  is deliberately similar.
- **Long-term suitability:** Strong for ERPX's actual current need
  (durable, queryable logs alongside existing metrics) and scales with the
  platform without a re-architecture; would need reconsideration only if a
  future requirement specifically needs deep full-text search across log
  bodies at scale.

### 2. Fluent Bit + Loki

- **Architecture:** Fluent Bit (C, DaemonSet/sidecar) ships logs, applying
  Kubernetes metadata enrichment and parsing; Loki (as above) stores/indexes.
- **Advantages:** Lightest-weight shipper evaluated (~450KB binary,
  single-digit-MB RSS); native `kubernetes` filter for pod/namespace/label
  enrichment; this pairing is Grafana's own documented reference
  architecture.
- **Disadvantages:** Two components instead of one managed service; parsing
  rules for the mixed JSON/plain-text situation (Section 1) live in config
  that needs maintaining as log formats evolve — though this is also true,
  to varying degrees, of every non-fully-managed option evaluated here.
- **Ops complexity:** Low — this is effectively today's standard K8s
  logging reference architecture.
- **Scalability:** Fluent Bit scales trivially (stateless, one pod/node);
  Loki as above.
- **Resource/Performance profile:** Lowest combined footprint of any full
  pipeline evaluated.
- **K8s/Docker/Grafana/Prometheus integrations:** Excellent — DaemonZet
  pattern matches the existing `prometheus.io/scrape` pod-annotation
  convention already used in `api-deployment.yaml`, extended to logs
  rather than introduced as a new idea; runs as a normal `docker-compose.yml`
  service for the Compose path.
- **Security/Compliance:** Fluent Bit supports TLS to its output;
  compliance posture inherits Loki's + Grafana's access control.
- **Multi-tenancy:** Same as Loki, same ERPX-side prerequisite noted above.
- **HA/DR:** Fluent Bit is stateless (a crashed pod loses only its
  in-flight buffer, not historical data); Loki's HA/DR as above.
- **Cost:** Same as Loki, plus negligible Fluent Bit compute.
- **Maintenance effort:** Low — small, declarative, version-controllable
  Fluent Bit config is the only added surface over Loki alone.
- **Learning curve:** Low — Fluent Bit config is declarative YAML/config
  file, no new query language (queries still happen in Grafana/LogQL).
- **Long-term suitability:** Same as Loki; this is simply *how* Loki
  actually receives logs in a real deployment (Loki alone, #1, still needs
  something shipping to it — this option makes that explicit).

### 3. OpenSearch

- **Architecture:** Full-text search/analytics engine (Elasticsearch fork,
  Apache 2.0) + OpenSearch Dashboards, fed by a shipper.
- **Advantages:** Powerful full-text search and aggregations; AWS offers a
  managed service (Amazon OpenSearch Service) fitting the existing
  Terraform/AWS path; fully open-source licensing (the reason it exists as
  a fork).
- **Disadvantages:** JVM-based — real heap/GC tuning burden nothing else
  in this stack currently requires; introduces a *second* dashboard UI
  alongside the already-provisioned Grafana, fragmenting where an incident
  responder looks.
- **Ops complexity:** High self-managed; Medium with AWS's managed
  offering (AWS handles patching/scaling; index lifecycle policy and
  mapping design remain the operator's responsibility).
- **Scalability:** Excellent, purpose-built for this.
- **Resource/Performance profile:** High — JVM heap typically needs 4GB+/node
  even at modest volume to avoid GC pauses.
- **K8s/Docker/Grafana/Prometheus integrations:** Good K8s (Helm chart,
  Operator available) and Docker (official images) support; Grafana can
  add OpenSearch as a datasource too, but the native OpenSearch Dashboards
  UI is the more natural fit, which is exactly the "second UI" disadvantage
  above.
- **Security/Compliance:** Genuinely mature — OpenSearch Security plugin
  gives real RBAC/TLS/audit logging, *if actually configured* (the
  codebase's own existing Elasticsearch instance shows the temptation to
  skip this: `xpack.security.enabled=false`).
- **Multi-tenancy:** Index-per-tenant or field-level security patterns
  exist and are mature, but — same as every option here — have no
  `organization_id` in the log data to key on without the Section 1 fix.
- **HA/DR:** Mature multi-node clustering with replica shards; real
  operational discipline required to run correctly (shard/replica sizing,
  snapshot policies for DR).
- **Cost:** Amazon OpenSearch Service is priced per-node-hour + storage,
  meaningfully above Loki-on-existing-MinIO for equivalent volume;
  self-managed avoids the AWS markup but reintroduces the JVM operational
  burden.
- **Maintenance effort:** Medium-High — index lifecycle policies, mapping
  evolution, periodic reindexing, JVM tuning.
- **Learning curve:** Medium-High — new query DSL, new operational
  concepts (shards, replicas, index templates) nothing else in this stack
  currently requires.
- **Long-term suitability:** Strong if deep full-text search genuinely
  becomes a hard requirement; disproportionate to finding #6's actual ask
  (durable, queryable logs) at ERPX's current scale.

### 4. Fluent Bit + OpenSearch

- **Architecture:** Fluent Bit shipper (as #2) feeding OpenSearch (as #3)
  instead of Loki.
- **Advantages:** Combines the lightest shipper with the deepest full-text
  search depth evaluated among self-hosted options.
- **Disadvantages:** Fluent Bit's lightness doesn't reduce OpenSearch's
  JVM/index-management burden, which dominates this pairing's true cost
  either way.
- **Ops complexity / Scalability / Resource/Performance / Security /
  Multi-tenancy / HA/DR / Cost / Maintenance / Learning curve / Long-term
  suitability:** Dominated by OpenSearch's profile (#3); Fluent Bit
  contributes the same low shipping overhead as #2.
- **K8s/Docker/Grafana/Prometheus integrations:** Fluent Bit side excellent
  (as #2); OpenSearch side as #3 (Grafana-as-secondary-UI, native
  OpenSearch Dashboards as primary).

### 5. Elasticsearch

- **Architecture:** Same category as OpenSearch (its origin project);
  typically Elastic Stack (Elasticsearch + Kibana + Beats/Logstash).
- **Advantages:** Same technical profile as OpenSearch; larger third-party
  plugin ecosystem; **already present in this exact codebase** —
  `docker-compose.yml` provisions `docker.elastic.co/elasticsearch/elasticsearch:8.13.4`,
  and `apps/api/app/api/v1/health.py`'s readiness check already pings it
  as an optional dependency (per the already-shipped health-check fix,
  `docs/architecture/health-checks.md`).
- **Disadvantages:** Post-7.11 default licensing is "Elastic License,"
  not fully OSS (OpenSearch specifically exists to avoid this); **the
  already-provisioned instance runs with security explicitly disabled**
  (`xpack.security.enabled=false`) and needs real hardening (enable
  `xpack.security`, TLS, users/roles) before trusting it with log data —
  not a zero-cost reuse of existing investment.
- **Ops complexity / Scalability / Resource/Performance / K8s & Docker
  integration / Multi-tenancy / HA/DR / Maintenance / Learning curve:**
  Materially identical to OpenSearch (#3) — same lineage, same
  architecture.
- **Security/Compliance:** Same mature *capability* as OpenSearch when
  properly configured — but "properly configured" is not this codebase's
  current state for the one instance that already exists.
- **Cost:** Elastic Cloud (managed) pricing comparable to or above Amazon
  OpenSearch Service; self-managed avoids license/SaaS cost but the free
  distribution's security/alerting feature set is narrower than
  OpenSearch's fully-open equivalent.
- **Long-term suitability:** Same technical ceiling as OpenSearch; the
  licensing model is a genuine long-term consideration OpenSearch was
  created specifically to sidestep.

### 6. Fluentd

- **Architecture:** Ruby-based shipper/aggregator (Fluent Bit's older,
  heavier CNCF-sibling project), large plugin ecosystem, typically feeds
  Elasticsearch/OpenSearch/S3/many other outputs.
- **Advantages:** Very large plugin ecosystem — broader than Fluent Bit's
  deliberately smaller reimplementation; mature, widely deployed
  industry-wide.
- **Disadvantages:** Meaningfully heavier resource footprint than Fluent
  Bit (Ruby runtime + gems vs. a C binary) for what would be an identical
  job in this stack; every output ERPX would plausibly need (Loki,
  OpenSearch, CloudWatch, S3) already has first-class Fluent Bit support,
  reducing Fluentd's plugin-breadth advantage to theoretical for this
  specific use case.
- **Ops complexity:** Medium — larger config surface than Fluent Bit for
  equivalent functionality here.
- **Scalability:** Good, proven at large scale industry-wide.
- **Resource/Performance profile:** Medium — noticeably higher baseline
  than Fluent Bit for equivalent throughput.
- **K8s/Docker/Grafana/Prometheus integrations:** Good K8s (official
  DaemonSet patterns, though less "reference architecture" status than
  Fluent Bit today) and Docker support; Grafana/Prometheus integration is
  purely a function of whichever backend it feeds (same as Fluent Bit).
- **Security/Compliance:** Comparable to Fluent Bit — TLS to outputs, no
  built-in auth of its own.
- **Multi-tenancy / HA/DR:** Function of the backend it feeds, same
  caveats as Fluent Bit's pairings above.
- **Cost:** Marginally higher compute than Fluent Bit for the same job;
  otherwise equivalent to whichever backend it feeds.
- **Maintenance effort:** Medium — larger config surface than Fluent Bit.
- **Learning curve:** Medium — Ruby-based config (`.conf` DSL) is a
  different mental model than Fluent Bit's simpler config format.
- **Long-term suitability:** Reasonable but strictly dominated by Fluent
  Bit for ERPX's specific target backends — no output ERPX plausibly needs
  is Fluentd-only.

### 7. AWS CloudWatch (Logs)

- **Architecture:** Fully-managed AWS log storage/query, shipped via the
  CloudWatch agent, the `awslogs` Docker logging driver, or Fluent Bit's
  CloudWatch output plugin; queried via CloudWatch Logs Insights.
- **Advantages:** Zero backend to run at all; **directly matches this
  codebase's actual cloud provider** — `infrastructure/terraform/versions.tf`
  already configures `provider "aws" { region = "us-east-1" }` and
  provisions RDS + ElastiCache there; IAM-based access reuses whatever
  policy structure already gates RDS/ElastiCache access; native CloudWatch
  Alarms integration for paging.
- **Disadvantages:** AWS-only — the self-hosted `docker-compose.yml` path
  this codebase also genuinely supports gets no benefit, forcing a second
  solution for that path unless it's formally deprioritized; CloudWatch
  Logs Insights' query language is less expressive than LogQL/full
  Elasticsearch DSL for complex analysis; **zero existing Terraform
  resource for this** — confirmed no `cloudwatch`/`log_group` match
  anywhere in `infrastructure/terraform/` — genuinely new infrastructure,
  not reused investment.
- **Ops complexity:** Lowest evaluated — no server, no cluster, no agent
  tuning beyond the shipper's own config.
- **Scalability:** Fully managed, transparent.
- **Resource/Performance profile:** None beyond the shipper — no backend
  to run.
- **K8s/Docker/Grafana/Prometheus integrations:** Good K8s (Fluent Bit's
  CloudWatch output plugin is AWS's own documented "Container Insights"
  pattern); excellent Docker (native `awslogs` driver, zero extra
  component); Grafana *can* add CloudWatch as a datasource (a plugin, not
  native), giving a path back to the unified-dashboard property Loki has
  natively; no direct Prometheus relationship (separate systems).
- **Security/Compliance:** IAM-based, encryption at rest by default, fits
  naturally alongside existing Terraform-managed IAM roles.
- **Multi-tenancy:** CloudWatch Logs supports per-log-group IAM policies —
  could in principle scope access per environment/team; same ERPX-side
  `organization_id`-in-logs prerequisite as every other option for
  per-customer scoping.
- **HA/DR:** Fully managed, AWS's own multi-AZ durability — no DR
  procedure for ERPX to design or own.
- **Cost:** Pay-per-GB-ingested + per-GB-stored + per-GB-queried — can
  become the most expensive self-hosted-adjacent option at high volume
  (CloudWatch Logs' pricing model is a commonly-cited industry criticism),
  though a non-issue at ERPX's current pre-production scale.
- **Maintenance effort:** Lowest — AWS operates the backend; only shipper
  config and retention/export policy need upkeep.
- **Learning curve:** Low for anyone already working in the AWS console
  for RDS/ElastiCache (already true for this deployment); CloudWatch Logs
  Insights' query syntax is its own thing to learn, though simpler than
  LogQL or Elasticsearch DSL.
- **Long-term suitability:** Strong specifically for the AWS/K8s path;
  weak as a *complete* answer given the Compose path's genuine existence —
  the central reason this isn't the top recommendation.

### 8. Azure Monitor

- **Architecture:** Azure's equivalent of CloudWatch — Log Analytics
  workspace + Kusto Query Language.
- **Advantages:** Same "fully managed, zero backend" profile as CloudWatch,
  *if* deployed on Azure.
- **Disadvantages:** **This codebase's cloud infrastructure is AWS, not
  Azure** — confirmed by direct read of `infrastructure/terraform/`
  (`aws_db_instance`, `aws_elasticache_replication_group`,
  `provider "aws"`, `region = "us-east-1"`). Adopting Azure Monitor means
  either genuine cross-cloud complexity (egress cost, IAM-model mismatch
  between AWS resources and an Azure log destination) or signals a
  cloud-migration decision entirely outside this finding's scope. Zero
  synergy with anything already in this stack.
- **Ops complexity / Scalability / Resource-Performance / Security /
  Multi-tenancy / HA-DR / Cost / Maintenance / Learning curve:** Broadly
  comparable to CloudWatch's profile in isolation, but not evaluated in
  further depth given the platform mismatch — the same reasoning any
  Azure-specific service gets skipped for an AWS-Terraform-based
  deployment.
- **K8s/Docker/Grafana/Prometheus integrations:** Azure Monitor for
  containers exists for AKS specifically; this deployment's K8s manifests
  are cloud-agnostic (no AKS-specific resources) and its actual
  provisioned cloud is AWS — this integration path doesn't apply.
- **Long-term suitability:** Not suitable absent a broader Azure migration
  decision this proposal has no basis to recommend.

### 9. Datadog

- **Architecture:** SaaS observability platform (logs + metrics + APM +
  more) via a single unified agent.
- **Advantages:** Would also close finding #10 (no APM/tracing/error
  aggregation — `docs/project-hardening-audit.md`) in the same rollout,
  since Datadog is unified; strong AWS/K8s integrations; minimal
  operational burden (fully SaaS).
- **Disadvantages:** Materially replaces, rather than extends, the
  already-deployed Prometheus + Grafana investment (scrape configs, the
  provisioned `erpx-api-overview.json` dashboard, alert rules) — that
  existing work becomes redundant or has to run in parallel with a second,
  overlapping tool; recurring per-host + per-GB SaaS cost, the only option
  in this list whose cost doesn't shrink toward zero at ERPX's current
  low pre-production volume (meaningful per-host minimums regardless of
  actual usage); introduces a new third-party data-processor relationship
  for logs that may contain PII (payroll, Pentrix VAPT findings, Corporate
  SOC incident data — all named explicitly in
  `docs/deployment/production-checklist.md`'s own security section),
  requiring a compliance/DPA review as a real prerequisite, not just a
  technical integration step.
- **Ops complexity:** Lowest of any option — agent install + dashboard
  config, no backend to run — at the cost of duplicating rather than
  reusing existing infrastructure investment.
- **Scalability:** Fully managed, transparent.
- **Resource/Performance profile:** Agent-only, lightweight; no self-hosted
  backend.
- **K8s/Docker/Grafana/Prometheus integrations:** Excellent K8s (official
  Helm chart, DaemonSet agent) and Docker (official Compose integration)
  support; Datadog *can* be added as a Grafana datasource, but its own
  native dashboards are the intended UI, again fragmenting where an
  operator looks versus the already-provisioned Grafana; has its own
  Prometheus-metrics-scraping capability, which would duplicate (not
  integrate with) the existing Prometheus deployment rather than replace
  it cleanly.
- **Security/Compliance:** Vendor-managed; SOC 2 / various compliance
  certifications exist at the vendor level, but ERPX's own DPA/compliance
  review (noted above) is still a real, separate prerequisite given the
  sensitive data categories already handled by this platform.
- **Multi-tenancy:** Datadog supports tag-based scoping (would need
  `organization_id` as a tag — same ERPX-side prerequisite as every
  option here).
- **HA/DR:** Fully managed, vendor-owned.
- **Cost:** Highest recurring cost of any option evaluated at ERPX's
  current (low, pre-production) volume specifically, due to per-host
  pricing minimums that don't scale down with actual usage the way
  usage-based pricing (CloudWatch, self-hosted-on-existing-infra options)
  does.
- **Maintenance effort:** Lowest technically; highest organizationally
  (vendor contract, ongoing compliance/DPA relationship management).
- **Learning curve:** Low — polished, well-documented SaaS UX.
- **Long-term suitability:** Strong *if* finding #10 (APM/tracing) is
  prioritized simultaneously and a SaaS observability budget is approved
  — otherwise disproportionate to finding #6 alone.

### 10. Splunk

- **Architecture:** Enterprise log management/SIEM platform, self-hosted
  (Splunk Enterprise) or SaaS (Splunk Cloud), via Universal Forwarder or
  HTTP Event Collector.
- **Advantages:** Extremely mature search (SPL); the deepest
  security-analytics/SIEM capability of anything evaluated — genuinely
  relevant given ERPX's Pentrix (security testing) and Corporate SOC
  modules already produce security-relevant data that a SIEM-class tool
  is purpose-built to correlate.
- **Disadvantages:** By far the most expensive option evaluated — Splunk's
  ingest-volume-based licensing is widely cited industry-wide as the
  primary reason organizations migrate away from it as volume grows;
  **zero existing footprint or synergy anywhere in this repository**
  (confirmed: no Splunk-related config, agent, or reference found); would
  represent a large net-new financial and operational commitment
  disproportionate to what finding #6 actually asks for (durable,
  queryable logs), effectively solving a SIEM/compliance problem ERPX
  hasn't been asked to solve yet.
- **Ops complexity:** High for self-hosted Enterprise (indexer clusters,
  search head clusters); Low for Splunk Cloud, at correspondingly high cost.
- **Scalability:** Excellent, proven at very large enterprise scale — well
  beyond ERPX's current or reasonably foreseeable log volume.
- **Resource/Performance profile:** High for self-hosted — indexers are
  resource-heavy, comparable to or exceeding Elasticsearch/OpenSearch per
  unit of log volume.
- **K8s/Docker/Grafana/Prometheus integrations:** Good K8s (official
  Splunk Connect for Kubernetes) and Docker (Universal Forwarder as a
  container) support; Splunk has its own dashboarding, again fragmenting
  from the existing Grafana investment; no native Prometheus relationship.
- **Security/Compliance:** Best-in-class for this category — real RBAC,
  platform-level audit trails, extensive compliance certifications — but
  this strength solves a SIEM use case, not the "don't lose logs on pod
  restart" problem finding #6 actually names.
- **Multi-tenancy:** Mature (index-per-tenant patterns, role-based access);
  same ERPX-side `organization_id`-in-logs prerequisite as every option here.
- **HA/DR:** Mature clustering/replication for self-hosted; fully managed
  for Splunk Cloud — genuinely enterprise-grade, at the cost premium noted.
- **Cost:** Highest of any option evaluated by a wide margin — licensing
  scales linearly (or worse) with log volume growth, the opposite of what
  a cost-conscious pre-production platform needs.
- **Maintenance effort:** High self-hosted; Low-Medium Splunk Cloud, at
  the cost premium above.
- **Learning curve:** Medium-High — SPL is powerful but is its own
  substantial query language to learn, on top of a large product surface.
- **Long-term suitability:** Excellent *if* ERPX's long-term roadmap
  includes formal SIEM/compliance requirements (plausible given Pentrix/
  Corporate SOC data) — but that is a distinct future decision, not
  something to pre-commit to for finding #6 alone.

---

## 3. Tailored ERPX Recommendation & Final Decision

### Chosen solution: **Fluent Bit + Grafana Loki**

### ERPX-specific justification (not generic popularity)

1. **Grafana is already deployed, already has a provisioned datasource and
   dashboard** (`infrastructure/monitoring/grafana/datasources/prometheus.yml`,
   `.../dashboards/erpx-api-overview.json`). Loki is a native Grafana
   datasource — logs land in the exact tool operators already use for
   metrics, with the exact auth model already in place. No other option
   has this property without adding a second UI (OpenSearch/Elasticsearch/
   Splunk's own dashboards) or a third-party SaaS UI (Datadog).
2. **MinIO already runs and is already integrated**
   (`packages/storage/client.py`, used by `modules/backups`,
   `modules/documents`, `modules/media`) — Loki's object-storage backend
   can be a new bucket on that same instance, genuinely reusing existing
   infrastructure rather than the "provisioned-but-unused-and-insecure"
   situation the audit already found with the Compose Elasticsearch
   container.
3. **Fluent Bit's DaemonSet + Kubernetes-metadata-discovery pattern directly
   extends an existing convention**, not introduces a new one:
   `api-deployment.yaml`'s `prometheus.io/scrape` pod annotations already
   establish "an agent auto-discovers workloads via K8s metadata" for
   metrics; this is the same idea applied to logs.
4. **Lowest total resource/operational footprint of any non-CloudWatch
   option** — no JVM anywhere in the pipeline, matching this platform's
   generally lean infrastructure profile (single RDS instance, single
   ElastiCache replication group, no Operator-managed stateful services
   anywhere in `infrastructure/kubernetes/` today).
5. **The only option that serves both real deployment paths equally well**
   — the AWS/K8s path and the self-hosted `docker-compose.yml` path
   (both confirmed real and supported per `docs/project-audit.md`).
   CloudWatch (the next-best option on pure infrastructure-fit grounds)
   only serves the first.

### Reasons for rejecting the other 9

| # | Solution | Primary rejection reason |
|---|---|---|
| 2 | Fluent Bit + Loki | Not rejected — this *is* the recommendation (#1 alone still needs a shipper; listing it separately in the requested 10 made that explicit). |
| 3 | OpenSearch | JVM operational burden and a second dashboard UI, for search depth ERPX's actual current need (durable + queryable, not deep full-text analytics) doesn't require. |
| 4 | Fluent Bit + OpenSearch | Inherits OpenSearch's rejection reason — the shipper choice doesn't change the backend's cost profile. |
| 5 | Elasticsearch | Same technical rejection as OpenSearch, plus real licensing considerations, plus the already-provisioned instance needs hardening work before being trustworthy — not the "free reuse" it might appear to be. |
| 6 | Fluentd | Strictly heavier than Fluent Bit for every output ERPX would plausibly target; no ERPX-relevant capability Fluent Bit lacks. |
| 7 | AWS CloudWatch | Real, AWS-native option — rejected only because it doesn't serve the Compose deployment path at all, forcing two logging architectures. Reconsider if that path is formally deprioritized. |
| 8 | Azure Monitor | Platform mismatch — this codebase's cloud infrastructure is AWS, confirmed by Terraform; no synergy. |
| 9 | Datadog | Duplicates rather than extends the existing Prometheus/Grafana investment; highest recurring cost at current low volume; adds a compliance/DPA review given the sensitive data categories already in this platform. Reconsider jointly with finding #10 if an APM budget is approved. |
| 10 | Splunk | Solves a SIEM/compliance problem disproportionate to finding #6's actual ask, at by far the highest cost; zero existing footprint in this codebase. Reconsider only as part of a deliberate future SIEM/compliance initiative. |

### Expected production/ops benefits

- Logs survive pod eviction, rescheduling, and node log rotation — the
  concrete risk finding #6 names is closed.
- Error tracebacks (Section 1's highest-value case) become durably
  searchable instead of existing only in a container's transient stdout
  buffer.
- One dashboard (Grafana) for both metrics and logs during an incident,
  rather than context-switching between tools.
- A real floor under the account-lockout compensating control: failed-login
  and other security-event log lines (Section 1) become durably retained,
  not just database-counter-backed.

### Estimated implementation / maintenance effort

- Implementation: **Small-Medium**, detailed in Section 4's time estimates.
- Ongoing maintenance: **Low** — no index/shard management, no JVM tuning;
  the smallest recurring operational burden of any option besides the
  fully-managed SaaS/CloudWatch choices, without their cost or
  vendor-lock-in/platform-mismatch tradeoffs.

---

## 4. Complete Implementation Blueprint

**Presented for approval — nothing in this section has been implemented.**

### Topology — Architecture & Component Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│ Kubernetes cluster (namespace: erpx)                                   │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │ erpx-api pod │  │ celery-worker│  │ celery-beat  │   ...N replicas  │
│  │ stdout: JSON │  │ pod stdout:  │  │ pod stdout:  │                  │
│  │ (already true)│  │ JSON (after  │  │ JSON (after  │                  │
│  │              │  │ prereq fix)  │  │ prereq fix)  │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │  container stdout/stderr (node-local, kubelet-rotated)       │
│         ▼                 ▼                 ▼                          │
│  ┌────────────────────────────────────────────────────┐                │
│  │  Fluent Bit DaemonSet (1 pod / node)                 │                │
│  │  tail input → kubernetes filter (pod/ns/label        │                │
│  │  enrichment) → json parser → loki output              │                │
│  └───────────────────────┬────────────────────────────┘                │
│                            │ push, TLS (Loki HTTP API)                  │
│                            ▼                                            │
│  ┌───────────────────────────────────────────┐                          │
│  │  Loki (Deployment, monolithic mode)         │                          │
│  │  index: labels only (namespace, pod, app)    │                          │
│  │  chunks ─────────────────────────┐          │                          │
│  └───────────────────────────────────┼──────────┘                        │
│                                        │                                 │
│  ┌───────────────────────────────────┼──────────┐                       │
│  │  Grafana (already deployed)        │          │                       │
│  │  existing: Prometheus datasource   │          │                       │
│  │  NEW: Loki datasource ─────────────┘ (query)  │                       │
│  │  existing: erpx-api-overview dashboard         │                      │
│  │  NEW: log panels + Explore                     │                      │
│  └────────────────────────────────────────────────┘                     │
└──────────────────────────────────────┬──────────────────────────────────┘
                                         │
                                         ▼
                          ┌───────────────────────────┐
                          │  MinIO (already running)   │
                          │  NEW bucket: erpx-logs      │
                          └───────────────────────────┘
```

### Data Flow / Logging Pipeline diagram

```
[app/celery process]
     │ structlog.get_logger().info(event, **kv)
     ▼
[stdout, JSON — after Celery prereq fix]
     │ container runtime capture
     ▼
[node-local log file, e.g. /var/log/containers/*.log]
     │ tailed by
     ▼
[Fluent Bit: tail → kubernetes filter → parser (json) → buffer]
     │ HTTP push (batched, TLS)
     ▼
[Loki: distributor → ingester → (async) chunk flush]
     │
     ▼
[MinIO bucket: erpx-logs, compressed chunks + boltdb-shipper index]
     │ queried by
     ▼
[Loki: querier ← LogQL ← Grafana Explore / dashboard panel]
```

### Network flows

- Fluent Bit (DaemonSet, one pod per node) → Loki Service (ClusterIP,
  in-cluster only, no external exposure needed) — HTTP/HTTPS on Loki's
  default port (3100), intra-namespace traffic, no ingress/egress rule
  changes needed beyond a `NetworkPolicy` explicitly permitting this if
  the cluster enforces default-deny (not currently the case — no
  `NetworkPolicy` resources exist anywhere in `infrastructure/kubernetes/`
  today, confirmed by directory listing).
- Loki → MinIO (existing Service, already reachable from every pod that
  currently uses `packages/storage/client.py`) — same network path
  already proven working for `modules/backups`/`modules/documents`/`modules/media`.
  No new network policy required beyond what those modules already rely on.
- Grafana → Loki Service — same-namespace ClusterIP traffic, mirroring
  Grafana's existing Prometheus datasource connection exactly.
- Docker Compose path: all of the above as Docker bridge-network traffic
  on the existing `erpx_network` (`docker-compose.yml`'s already-defined
  network), no new network topology concept introduced.

### Infrastructure changes

- **Prerequisite (separate small fix, not part of this proposal's
  implementation but blocking correct Celery log parsing if skipped):**
  call `configure_logging()` from `apps/api/app/core/celery_app.py`.
- **New files (K8s):**
  - `infrastructure/kubernetes/fluent-bit-daemonset.yaml` — DaemonSet +
    ConfigMap (parser/output rules) + ServiceAccount + minimal RBAC
    (`get`/`list`/`watch` on pods, for the `kubernetes` filter's metadata
    enrichment) + ClusterRoleBinding, following the existing manifest
    style in that directory.
  - `infrastructure/kubernetes/loki-deployment.yaml` — Deployment +
    Service (ClusterIP) + ConfigMap (Loki config: S3-compatible backend
    pointed at MinIO, retention policy) + PersistentVolumeClaim (small,
    for the boltdb-shipper index cache only — bulk data lives in MinIO).
- **New file (Grafana):**
  `infrastructure/monitoring/grafana/datasources/loki.yml` — mirrors the
  existing `prometheus.yml` in that same directory exactly (same
  auto-provisioning mechanism).
- **Docker Compose changes:** two new service blocks in `docker-compose.yml`
  (`fluent-bit`, `loki`), following the existing service-definition style;
  `fluent-bit` reads the Docker socket (`/var/run/docker.sock`, read-only
  mount) instead of a K8s-mounted log directory.
- **Terraform (AWS path, only if S3 is preferred over reusing MinIO for
  log storage specifically):** a new `aws_s3_bucket` resource + IAM policy
  for the Loki service account, following the existing pattern in
  `infrastructure/terraform/storage.tf`. **Default recommendation: reuse
  MinIO** (point 2 in Section 3) rather than add this — only revisit if a
  future requirement specifically needs S3-native features MinIO doesn't
  replicate.
- **Env vars:** Loki's config references the storage endpoint/bucket
  (already-established pattern — matches `MINIO_ENDPOINT`/`MINIO_BUCKET`
  naming already used in `apps/api/app/core/config.py`); Fluent Bit's
  config references the Loki Service DNS name (in-cluster) or `loki:3100`
  (Compose) — no new secret-bearing env vars beyond what MinIO access
  already requires.
- **Secrets:** Loki's MinIO/S3 credentials — reuse the existing
  `erpx-secrets` K8s Secret (`infrastructure/kubernetes/secret.yaml.example`
  already documents the pattern for this class of value) rather than
  creating a new Secret object; for the Compose path, reuse the existing
  `.env`-sourced MinIO credentials already used by the `api`/`celery_worker`
  services.

### Data Governance

- **Security controls:** Fluent Bit → Loki traffic over TLS within the
  cluster network; a `NetworkPolicy` restricting Loki's Service to only
  accept connections from Fluent Bit and Grafana specifically (new — none
  exist in this repo today, so this would be the first, not a change to
  an existing policy); Grafana's existing login/auth gates who can query
  logs, no new auth system introduced.
- **Sensitive-data handling:** Carries forward the existing
  `docs/deployment/production-checklist.md` checklist item verbatim —
  "verify `app/core/logging_config.py` doesn't log full request bodies
  for `/auth/*` endpoints" — this must be true *before* logs are shipped
  anywhere external, since shipping durably stores whatever was already
  being logged, including anything an existing-but-unnoticed leak was
  already writing to stdout.
- **Retention:** Recommend 30 days hot/queryable via Loki's
  `retention_period` config — deliberately shorter than `AuditLog`'s
  indefinite retention (Section 1's table), since these are an operational
  tool, not the compliance record. Revisit once real production
  payroll/financial traffic exists and any applicable compliance
  requirement is identified.
- **Rotation:** Fully superseded by Loki's own retention/compaction —
  removes the current implicit dependency on node-level kubelet rotation
  as the *only* retention mechanism (today's actual state, per Section 1).
- **Compression:** Loki compresses chunks before writing to object storage
  by default (gzip or snappy, configurable) — no additional configuration
  needed beyond accepting the default.
- **Encryption:** In-transit via TLS (Fluent Bit→Loki, Grafana→Loki, both
  new); at-rest via whatever MinIO/S3 bucket encryption is configured —
  the existing production checklist already lists "MinIO/S3: bucket
  versioning + encryption enabled" as a pre-deploy item; the new
  `erpx-logs` bucket should follow the identical policy as the existing
  `erpx-storage` bucket, not a separate standard.
- **RBAC / Access control:** Inherits Grafana's existing user/role model —
  no new access-control system. If finer-grained scoping (e.g., a given
  admin can see only their own organization's logs) is ever required, that
  depends on the Section 1 `organization_id`-in-logs prerequisite plus
  Grafana folder/dashboard permissions or Loki's multi-tenant mode — both
  explicitly out of scope for this initial rollout, noted here as a known
  future extension point, not a current requirement.

### Reliability & Ops

- **Backup/DR:** Loki itself is stateless (all durable state in object
  storage) — DR for the Loki *service* is "redeploy the Deployment," no
  special backup procedure. Log *data* durability is inherited entirely
  from the MinIO/S3 bucket's own backup/versioning policy, which already
  needs to exist independent of this proposal (existing checklist item).
- **HA:** Loki Deployment can run 2+ replicas behind its Service once
  volume justifies it; at ERPX's current scale, a single replica is
  reasonable to start, with the understanding that a Loki restart causes a
  brief gap in *querying* (not data loss — object storage is unaffected).
- **Performance/Scalability plan:** Start in monolithic mode (single
  binary handling all Loki roles); Loki's own documented upgrade path to
  microservices/simple-scalable mode exists if/when volume genuinely
  requires it — no premature complexity now.
- **Monitoring:** Loki exposes its own Prometheus metrics endpoint — the
  already-running Prometheus (`infrastructure/monitoring/prometheus.yml`)
  gains one more scrape target (Loki itself), keeping "who watches the
  logging pipeline" inside the same monitoring system as everything else,
  not a separate concern.
- **Alerting:** Loki's ruler component can fire alerts (e.g., error-rate
  spikes detected in logs) through the same Alertmanager path Prometheus
  metric-based alerts already use once Alertmanager is deployed (currently
  commented out, pending, in `prometheus.yml`) — one alerting pipeline,
  not two.
- **Dashboards:** New Grafana dashboard(s) for log volume/error-rate
  trends, built alongside (not replacing) the existing
  `erpx-api-overview.json` dashboard.
- **Rollback/Migration plan:** Every component proposed here is additive
  — Fluent Bit reads logs that already exist; Loki is a new destination,
  not a replacement for anything; the application's own logging code
  (`logging_config.py`) is unchanged (aside from the separate Celery
  prerequisite fix, which is itself just "make Celery logs consistent
  with API logs," not a new behavior). Rollback is deleting the new K8s
  resources/Compose services and the Grafana datasource — the application
  continues logging to stdout exactly as today regardless of whether
  anything downstream is reading it.
- **Testing/Validation checklist** (for the eventual implementation phase):
  - [ ] Fluent Bit correctly parses JSON from API pods
  - [ ] Fluent Bit correctly parses JSON from Celery worker/beat pods
        (validates the prerequisite fix landed first)
  - [ ] A log line's `request_id` is queryable and matches the same
        request's `AuditLog.request_id` for a real test mutation
  - [ ] A deliberately-triggered unhandled exception's full traceback is
        retrievable from Loki after the pod that logged it is deleted
  - [ ] Grafana's Loki datasource returns results for a live LogQL query
  - [ ] Retention policy actually expires data at the configured interval
        (validated against a short test retention window before setting
        the real 30-day value)
  - [ ] Docker Compose path: identical checks against the `fluent-bit`/`loki`
        services
- **Ops runbook (to be written as part of implementation, not now):** how
  to query logs for a given `request_id`; how to check Fluent Bit/Loki's
  own health if the pipeline itself appears to be dropping data; how to
  manually trigger a retention/compaction cycle if storage grows
  unexpectedly.
- **Production readiness checklist additions** (to be merged into
  `docs/deployment/production-checklist.md`'s existing Observability
  section once implemented): Loki + Fluent Bit deployed and scraping;
  Grafana Loki datasource provisioned; retention policy set intentionally
  (not left at any tool default); `erpx-logs` bucket encryption/versioning
  confirmed, matching `erpx-storage`'s existing policy.
- **Time estimates:**
  - Celery `configure_logging()` prerequisite fix: **Small** (under an
    hour of work; blocks correct Celery log parsing if skipped —
    sequencing matters, this should land first)
  - Fluent Bit + Loki K8s manifests + Grafana datasource: **Medium** (half
    a day to a day, including the validation checklist above)
  - Docker Compose equivalent: **Small** (a few hours — mostly adapting
    the K8s config's logical setup into Compose service blocks)
  - Retention/alerting/dashboard tuning: **Small** (a few hours, mostly
    decisions rather than implementation)
  - Ops runbook + production checklist update: **Small** (an hour or two
    of documentation)
  - **Total: roughly 2-3 days of focused work**, most of it the K8s
    manifests + end-to-end validation.

---

## 5. Risk Assessment

| Severity | Domain | Cause | Impact | Mitigation | Recovery Strategy |
|---|---|---|---|---|---|
| **High** | Ops | Fluent Bit parsing rules mis-configured for one of the three log formats (API JSON, pre-fix Celery plain-text, nginx/ingress plain-text) | Silent data loss or unstructured/unqueryable log lines for that source, discovered only when someone actually needs those logs during an incident — the worst possible time | Explicit per-source validation in the testing checklist above (not just the happy-path API case); land the Celery `configure_logging()` prerequisite fix *before* enabling Fluent Bit's JSON parser for Celery pods | Fluent Bit config is declarative and version-controlled — revert to the last-known-good config; raw container logs are still available at the node level for the retention window that already exists today as a fallback |
| **High** | Security | The Section 1 finding that no log line carries `organization_id` is not addressed before shipping | An operator with Grafana access can technically query logs across every organization with no built-in scoping, on a platform whose data model is otherwise organization-scoped everywhere else (RBAC, most DB tables) | Restrict Grafana/Loki access to the same Administrator/Super-Admin tier already used for `backups.view`/`integrations.view` (`modules/authorization/service.py`'s existing pattern of excluding sensitive capabilities from the default Staff role) until/unless `organization_id`-in-logs is separately implemented | Access is a Grafana permission change (fast); no data-layer fix needed to recover from an over-broad grant, only to prevent one |
| **Medium** | Security | Sensitive data already present in existing log lines (Section 1's carried-forward checklist item about `/auth/*` request bodies) becomes durably stored once shipped, instead of merely transient in stdout | A pre-existing-but-unnoticed logging mistake becomes a real, durable, queryable data-retention problem the moment shipping is turned on | Complete the existing `docs/deployment/production-checklist.md` verification step *before* enabling shipping, not after; treat it as a hard gate for this rollout specifically, not just a general checklist item | If sensitive data is found already shipped: purge the specific log streams/time range from Loki (supported via its retention/deletion API) and fix the logging call site; this is why a short initial retention window during rollout (validation checklist item) limits blast radius before committing to the full 30-day policy |
| **Medium** | Ops | Loki label cardinality mistake (e.g. using `request_id` as an indexed Loki label instead of leaving it in the unindexed log body) | Real performance degradation and storage cost — Loki's most common operational failure mode industry-wide, would defeat the "low resource" advantage that is a core reason for this recommendation | Explicit Fluent Bit output config review before rollout: only low-cardinality fields (namespace, pod, app, level) as Loki labels; `request_id`/`organization_id`/other high-cardinality fields stay in the log body, queried via LogQL's line-filter syntax, not as labels | Loki labels can be reconfigured and historical high-cardinality streams dropped/re-ingested if caught early; caught late, may require a Loki redeploy with corrected config and accepting the cardinality cost for already-ingested data until it ages out via retention |
| **Medium** | Cost | New object storage bucket (`erpx-logs`) grows unexpectedly due to a retention misconfiguration or unexpectedly high log volume from a misbehaving component | Storage cost creep, mirroring the exact concern the audit already raised for `modules/backups` (finding #12 — no retention/cleanup policy) | Set and test the 30-day retention policy explicitly as part of the validation checklist (not left at a tool default); alert (via the same Prometheus/Alertmanager path) on bucket size growth rate, not just absolute size | Loki's retention policy, once corrected, self-heals storage growth over the following retention window; manual bucket cleanup only needed for a genuinely runaway/misconfigured case caught late |
| **Medium** | Maintenance | Fluent Bit/Loki configuration drifts from the parsing needs of new modules added over time (new log event shapes not anticipated by today's parser rules) | Gradual, silent degradation of log structure quality for newer parts of the codebase, easy to miss since older, well-parsed logs remain fine | Document the parser config's assumptions clearly (part of the ops runbook, Section 4) so future module authors know structured logging conventions extend to the shipping layer too, not just the application layer | Parser config is declarative/version-controlled — a fix is a config change + Fluent Bit rolling restart, no data migration needed |
| **Low** | Performance | Fluent Bit adds a small amount of per-node CPU/memory overhead (DaemonSet, one pod per node) | Marginal resource contention on already-running nodes | Fluent Bit's resource footprint is well-documented as minimal (~50-100MB RSS typical) — set conservative resource requests/limits in the DaemonSet spec, matching the existing resource-limit discipline already used in `api-deployment.yaml`/`celery-deployment.yaml` | Resource limits are a manifest-only change; no data-layer recovery needed |
| **Low** | Ops | The Compose-path nginx container's logs remain unstructured and uncorrelated (Section 1 — no `log_format` directive exists today) even after this proposal ships, since fixing that is a separate nginx config change not included here | Reverse-proxy-level request logs stay outside the unified log-search experience this proposal otherwise delivers for the Compose path specifically | Explicitly out of scope for this proposal (a config-file change to `infrastructure/nginx/nginx.conf`, not a shipping-pipeline decision) — noted here so it isn't silently forgotten as a known follow-up | No recovery needed — this is a known, accepted gap in the initial rollout, not a failure of anything implemented |
| **Low** | Ops | Kubernetes-path ingress-nginx controller logs remain entirely outside this proposal's visibility, since that component is an external cluster add-on this repository doesn't deploy or configure | Same category of gap as the Compose-path nginx item above, for the K8s path specifically | Document as a known boundary (this proposal covers what this repository deploys; the ingress controller is cluster-operator-owned infrastructure) rather than attempting to configure infrastructure outside this repo's scope | N/A — explicitly out of scope, not a defect to recover from |

---

## 6. Prerequisites Implementation Status (2026-07-28)

Implements *only* the prerequisites this proposal already identified as
required before shipping (Section 5's two High-severity risk rows). Loki and
Fluent Bit themselves are still **not implemented** — this section documents
groundwork only, per the explicit guardrail that governed this work.

### Unified logging schema

Every log line now carries, where applicable: `timestamp`, `level`,
`message`, `service`, `environment`, `request_id`, `organization_id`,
`user_id`, `module`, `logger`, `hostname`, `pod_container_metadata`,
`exception_details`. Implemented in `apps/api/app/core/logging_config.py`:

- `service`/`environment`/`hostname` are injected by a new
  `_static_fields_processor` closure — process-wide constants, not
  request-scoped, so they aren't contextvars-based.
- `pod_container_metadata` reads `POD_NAME`/`POD_NAMESPACE` env vars (the
  Kubernetes Downward API convention) and is `null` until a future
  deployment injects them via the pod spec — that manifest change is
  deferred to the actual Loki/Fluent Bit implementation (out of scope here;
  no Kubernetes resources were touched by this change).
- `module` comes from `structlog.processors.CallsiteParameterAdder`.
- `logger` comes from `get_logger(name)` now returning
  `structlog.get_logger(name).bind(logger=name)`.
- structlog's default `exception` key (written by the existing
  `format_exc_info` processor) is renamed to `exception_details` via a new
  one-line `_rename_exception_key` processor — `app/core/
  exception_handlers.py`'s `logger.exception(...)` call sites are
  unaffected, only the output key name changed.
- structlog's default `event` key is renamed to `message` via
  `EventRenamer("message")`, but **only in the production JSON renderer
  path** — local dev's `ConsoleRenderer` output is deliberately left
  unchanged (still keys off `event`) so familiar dev console output doesn't
  change.

### Celery worker/beat JSON logging (previously undocumented bug fix)

`configure_logging()` was previously called only from `app/main.py`. The
real `celery -A app.core.celery_app worker` / `... beat` entrypoints import
only `app/core/celery_app.py`, never `app/main.py` — so Celery processes
silently fell back to structlog's un-configured default renderer (plain
`key=value` text, no JSON, no schema fields at all) despite calling the
identical `get_logger()` API every task module uses. This was a real,
previously-undocumented bug, found empirically while writing this proposal's
Section 1 and confirmed again while implementing this fix (before: plain
text with no `service`/`timestamp`/schema fields when importing only
`app.core.celery_app`; after: full JSON schema with `service="erpx-celery"`).

Fixed with one addition to `apps/api/app/core/celery_app.py`:
`configure_logging(service_name="erpx-celery")`, called at module import
time — `service_name` is a new parameter on `configure_logging()`
(default `"erpx-api"`, so `app/main.py`'s existing no-argument call site
needed no change). `app/main.py` imports `app.api.v1.router` — which
transitively imports `app.core.celery_app` — before its own
`configure_logging()` call; this means the Celery-flavored config can fire
first as a side effect during API startup, but `structlog.configure()`
fully replaces the processor chain on every call, and `app/main.py`'s own
call is always the true last one in the API process's startup sequence, so
the API process's logs are unaffected (`service="erpx-api"`, correctly).
Verified with a real subprocess import of `app.main` reproducing this exact
order.

### `organization_id` / `user_id` / `request_id` correlation

`apps/api/app/core/audit_context.py`'s three existing setters
(`set_audit_request_metadata`, `set_audit_user`, `set_audit_organization`)
now also call `structlog.contextvars.bind_contextvars(...)`, in addition to
their existing plain `ContextVar.set(...)` calls that already feed
`AuditLog` rows. This reuses the exact same two call sites that already
resolve these values (`modules/users/dependencies.py`'s
`get_current_user_organization_id` and `modules/authentication/
dependencies.py`'s `get_current_active_user`) — no new resolution
mechanism, no duplicated context tracking. A request whose dependency chain
never resolves an organization (e.g. a self-service endpoint with no
`get_current_user_organization_id` dependency) legitimately has no
`organization_id` in either `AuditLog` rows or logs — this mirrors
`AuditLog.organization_id`'s existing nullability and is by design, not a
gap.

### Nginx (Compose path) JSON access/error logs

`infrastructure/nginx/nginx.conf` gained a `map $status $loglevel` block
and a `log_format json_combined escape=json` directive (fields: `timestamp`,
`level`, `message`, `service="erpx-nginx"`, `remote_addr`, `method`, `path`,
`status`, `request_time`, `request_id`, `user_agent`), applied via
`access_log /dev/stdout json_combined;` / `error_log /dev/stderr warn;`.
`request_id` is captured from `$upstream_http_x_request_id` — the API's own
`X-Request-ID` response header, set by `RequestContextMiddleware` — so
nginx access logs now correlate with the API/Celery JSON logs they front.
Config syntax verified with `nginx -t` in a throwaway `nginx:alpine`
container; the only error surfaced (`host not found in upstream
"api:8000"`) is pre-existing and unrelated (the `api`/`web` upstream
hostnames only resolve inside `docker-compose`'s network, not a bare
container run). The Kubernetes path's ingress-nginx controller is external,
cluster-operator-owned infrastructure this repository doesn't deploy or
configure (see Section 1) and remains out of scope, as already documented.

### Testing

New file `tests/unit/test_logging_config.py` (11 tests, all passing):
unified schema keys present in production JSON output; `service` correctly
distinguishes `erpx-api` from `erpx-celery`; `exception`→`exception_details`
rename; `pod_container_metadata` null vs. populated from Downward API env
vars; dev-mode console rendering unaffected (still keys off `event`, not
JSON); `request_id`/`user_id`/`organization_id` populate from
`audit_context.py`'s setters and are absent (not null) when never set;
`organization_id` specifically absent when only `user_id` resolves, mirroring
`AuditLog`'s own nullability; `get_logger()` binds `logger`; and a real
subprocess-based regression test reproducing the exact `celery -A
app.core.celery_app worker` import path, confirming JSON output with
`service="erpx-celery"` (this is the automated regression guard against the
bug described above recurring silently).

Full regression suite (`tests/unit tests/api tests/integration
tests/security`) re-run after these changes; see
`docs/project-hardening-audit.md` finding #6 for the pass/fail count.

**Waiting for your review/approval before implementing Section 4 (Loki +
Fluent Bit) itself.**
