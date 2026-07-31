# ERPX v1.0.0 — Rollback Plan

Rollback has two independent axes: **application image** and **database schema**.
Roll them back in the correct order for the situation. All ERPX migrations are
reversible (every revision has a real `downgrade()` body), but **prefer image
rollback without a schema downgrade** whenever the previous image is compatible
with the current schema — schema downgrades can drop columns/tables and lose
data.

---

## Decision guide

| Situation | Action |
|---|---|
| New image is bad, schema unchanged this release | **Image rollback only** (do NOT downgrade DB) |
| New image is bad *and* this release added migrations that the old image can't tolerate | Image rollback **then** targeted `alembic downgrade` to the prior head |
| Migration itself failed mid-apply | `alembic downgrade` to the last-good revision, fix, re-apply |
| Data corruption suspected | Restore from backup (see below), not a schema downgrade |

Identify the previous good revision/tag before you start:
```bash
git tag --list 'v*' --sort=-v:refname | head          # previous release tag
alembic history | head                                  # revision graph
```

---

## 1. Application image rollback (fast, safe, preferred)

### Kubernetes
```bash
kubectl -n <ns> rollout undo deployment/erpx-api            # to prior ReplicaSet
# or pin explicitly:
kubectl -n <ns> set image deployment/erpx-api \
  erpx-api=ghcr.io/gir-technologies/erpx-api:<previous-sha-or-tag>
kubectl -n <ns> rollout status deployment/erpx-api --timeout=180s
```

### Docker Compose
```bash
# Re-tag/point the api service at the previous image, then:
docker compose up -d api celery_worker celery_beat
docker compose ps
```

---

## 2. Database schema rollback (only if required)

Only when the previous image is incompatible with the new schema. This can be
destructive — confirm a fresh backup exists first (step 3).

```bash
# From apps/api, DATABASE_URL pointed at the target DB:
alembic current                     # note current head (e.g. 0038)
alembic downgrade -1                # step back one revision
#   or to a specific revision:
alembic downgrade <revision_id>
alembic current                     # verify
```

Restart workers/beat after a schema change so cached metadata is refreshed.

---

## 3. Data restore (last resort — corruption / bad data migration)

Use the platform's backup tooling / your managed-Postgres PITR:
```bash
# Managed Postgres: restore to a point-in-time just before the incident.
# Self-managed: restore the latest verified dump, e.g.
#   pg_restore -d "$PGURL" --clean --if-exists latest_verified.dump
# The Backups module tracks backup_jobs + restore_attempts for auditability.
```

---

## 4. Post-rollback verification

- `kubectl rollout status` clean / `docker compose ps` all healthy.
- Run `docs/release/SMOKE_TEST.md`.
- Confirm `alembic current` matches the running image's expected schema.
- Announce rollback complete; capture root cause before re-attempting the release.
