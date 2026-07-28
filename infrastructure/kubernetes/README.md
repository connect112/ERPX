# ERPX on Kubernetes

These manifests cover the **stateless application tier** only: `erpx-api`,
`erpx-celery-worker`, `erpx-celery-beat`, and `erpx-web`. Postgres, Redis,
MinIO, and Elasticsearch are intentionally **not** defined here — run
them as managed services (RDS/Cloud SQL, ElastiCache/Memorystore, an S3
bucket instead of self-hosted MinIO, a managed Elasticsearch/OpenSearch
service) rather than as StatefulSets on the same cluster. That's the
standard production posture for stateful data services and keeps this
directory honest about what it actually manages.

## Apply order

```bash
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
# Copy secret.yaml.example -> secret.yaml, fill in real values, then:
kubectl apply -f secret.yaml
kubectl apply -f api-deployment.yaml
kubectl apply -f celery-deployment.yaml
kubectl apply -f web-deployment.yaml
kubectl apply -f ingress.yaml
```

Before the first deploy, run migrations as a one-off Job (not baked into
the Deployment's startup command, so a bad migration never crash-loops
every API replica simultaneously):

```bash
kubectl run erpx-migrate --rm -i --restart=Never -n erpx \
  --image=ghcr.io/gir-technologies/erpx-api:latest \
  --env-from=configmap/erpx-config --env-from=secret/erpx-secrets \
  -- alembic upgrade head
```

## What's here

| File | Purpose |
|---|---|
| `namespace.yaml` | The `erpx` namespace everything else lives in |
| `configmap.yaml` | Non-secret config, mirrors `app/core/config.py` defaults |
| `secret.yaml.example` | Template for `DATABASE_URL`, `JWT_SECRET_KEY`, etc. — never commit the filled-in copy |
| `api-deployment.yaml` | API Deployment + Service + HorizontalPodAutoscaler (3–10 replicas on CPU/memory) |
| `celery-deployment.yaml` | Worker (scalable) and beat (fixed at 1 replica — a scheduler must never run more than once) |
| `web-deployment.yaml` | Static frontend build served by nginx (see `apps/web/Dockerfile.prod`) |
| `ingress.yaml` | TLS termination + routing for `api.erpx.example.com` and `app.erpx.example.com` |
| `loki-bucket-init-job.yaml` | One-off Job: creates the `erpx-logs` MinIO/S3 bucket — apply before `loki-deployment.yaml` |
| `loki-deployment.yaml` | Loki ConfigMap + Deployment + Service + a small PVC — see that file's own header comment for why this is the one deliberate exception to "stateless only" below |
| `fluent-bit-daemonset.yaml` | Fluent Bit DaemonSet + its own ServiceAccount/ClusterRole/ClusterRoleBinding (read-only pod/namespace metadata) + ConfigMap |

Replace every `erpx.example.com` and `ghcr.io/gir-technologies/...` value
with your actual domain and container registry before applying.

Log shipping (Loki + Fluent Bit) apply order and details:
`infrastructure/monitoring/README.md`. Querying shipped logs / on-call
troubleshooting: `docs/operations/logging-runbook.md`.
