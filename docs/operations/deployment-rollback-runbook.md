# Deployment Rollback Runbook

What to do when a deployment turns out to be bad — not a general incident
response guide, specifically "how do I get back to the last-known-good
state." See `docs/deployment/production-checklist.md`'s Rollback section
for the pre-deploy checklist item this backs.

## The mechanism already exists — this runbook documents it, not adds it

`.github/workflows/docker-publish.yml` tags every image built from `main`
with **both** `:latest` and `:${{ github.sha }}` — an immutable,
per-commit tag already exists in the registry for every build, it is not
something that needs to be introduced. `infrastructure/ci-cd/deploy.sh`
is written to be invoked with that SHA (`./deploy.sh <git-sha>`), and
uses `kubectl set image` per Deployment, which means `kubectl`'s own
rollout history already records the exact previous image tag — rollback
via `kubectl rollout undo` or a re-run of `deploy.sh` with the prior SHA
both work correctly today, precisely because the tagging strategy is
already correct. **The `:latest`/`:${...:latest tag}` values baked into
the static manifests (`infrastructure/kubernetes/{api,celery,web}-deployment.yaml`)
are bootstrap-only placeholders for a cluster's very first deploy before
`deploy.sh` has ever run** — every real deploy after that overwrites them
with an explicit SHA tag. There is no infrastructure change to make here;
this was a documentation gap, not a tagging gap.

## Step 1 — Confirm it's actually the deploy

Before rolling back, confirm the new deploy is actually the cause, not a
coincidental unrelated issue (a downstream dependency outage, a bad
migration that already ran regardless of code rollback, a traffic spike):

- `kubectl rollout status deployment/erpx-api -n erpx` — did the rollout
  itself actually complete, or is it still progressing/stuck?
- Check the "ERPX Logs Overview" Grafana dashboard / Loki (`{job="erpx", level="error"}`)
  for an error-rate change that started at the deploy's timestamp, not
  before it.
- `GET /api/v1/health/ready` — is the new revision even passing its own
  readiness probe? If not, Kubernetes may already be preventing it from
  serving traffic (check `kubectl get pods -n erpx` for `CrashLoopBackOff`
  or `0/1 Ready`).

## Step 2 — Determine whether a database migration shipped with this deploy

This is the fork in the decision tree — code-only rollback and
migration-included rollback are different procedures with different risk.

```bash
# What SHA is currently deployed, and what was the previous one?
kubectl rollout history deployment/erpx-api -n erpx

# Did this deploy add any Alembic migration files?
git log --name-only <previous-good-sha>..<bad-sha> -- apps/api/alembic/versions/
```

If that `git log` is empty: **no migration shipped, skip to Step 3a.**
If it lists one or more new migration files: **read them before doing
anything — go to Step 3b.**

## Step 3a — Code-only rollback (no migration involved)

The simple, low-risk case. Old code is compatible with the unchanged
schema.

```bash
# Preferred: explicit, auditable — re-deploys the exact known-good SHA,
# including re-running (harmless, idempotent) `alembic upgrade head`
# against a schema that hasn't changed.
./infrastructure/ci-cd/deploy.sh <previous-good-sha> erpx

# Simpler alternative if you don't have the previous SHA handy —
# kubectl's own rollout history already has it:
kubectl rollout undo deployment/erpx-api -n erpx
kubectl rollout undo deployment/erpx-celery-worker -n erpx
kubectl rollout undo deployment/erpx-celery-beat -n erpx
kubectl rollout undo deployment/erpx-web -n erpx
```

`kubectl rollout undo` reverts each Deployment independently — run it for
all four (api, celery-worker, celery-beat, web) since the previous good
state means all four running the previous SHA together, not a partial mix.

## Step 3b — A migration shipped with the bad deploy

Do **not** default to `alembic downgrade`. Read each new migration file's
`upgrade()`/`downgrade()` first and classify it:

**Purely additive** (new table, new nullable column, new index) — safe to
leave the schema as-is and just roll back the *code* (Step 3a). Old code
simply doesn't reference the new table/column; nothing breaks. This is
the common case and does **not** require running `alembic downgrade`.

**Destructive or renaming** (dropped column, renamed table, `NOT NULL`
added to an existing column, a data-migrating `op.execute(...)`) — this
needs a real decision, not a default action:

1. Has any row actually been written under the new schema shape since
   the bad deploy went live? Check row counts / recent `updated_at`
   timestamps on the affected table. If the new deploy was live for only
   a few minutes and the affected feature saw no traffic, downgrading is
   likely safe.
2. If real data already exists in the new shape, `alembic downgrade -1`
   **can lose that data** (e.g. a dropped column's downgrade recreates an
   empty column, not the original values) — in that case, rolling back
   the *code* only (leaving the newer, safe superset schema in place) is
   usually the correct call, even though it means the schema is now
   "ahead of" the running code. Confirm the old code doesn't actively
   break against the newer schema (e.g. a `NOT NULL` addition without a
   default *would* break old INSERT statements missing that column — that
   specific case has no safe rollback short of a manual data-preserving
   fix, which is why `NOT NULL` migrations without a `server_default`
   are worth avoiding in general).
3. If you determine downgrade is genuinely safe:
   ```bash
   # From apps/api/, against the real DATABASE_URL - never guessed/assumed
   alembic current
   alembic downgrade -1
   ```
   Then proceed with Step 3a's code rollback.

**When in doubt, prefer rolling back code only and leaving the schema
forward** — an extra unused column/table is a cleanup task; lost
production data is not recoverable without a full restore
(`docs/operations/disaster-recovery-runbook.md`).

## Step 4 — Verify the rollback

- `kubectl rollout status deployment/erpx-api -n erpx` (and the other 3)
  — confirms the rollback's own rollout completed.
- `GET /api/v1/health/ready` returns 200.
- Error rate back to baseline in Grafana/Loki.
- `alembic current` matches what the now-running code actually expects.

## Step 5 — After the rollback

A rollback is a mitigation, not a resolution. Before the next deploy
attempt:
- Root-cause what made the bad deploy bad (test gap, migration risk not
  caught in review, environment-specific issue CI didn't reproduce).
- If a migration was involved and left in the "ahead" state (Step 3b,
  case 2), track the cleanup as its own follow-up — don't let the schema
  silently drift from what any given code revision assumes indefinitely.
