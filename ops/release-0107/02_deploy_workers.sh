#!/bin/bash
# ERPX release 0107 (PR #180)  --  STEP 2: build and recreate celery_worker, then celery_beat, one at a time, with the same code as the api.
# They run no migration (RUN_MIGRATIONS is only set on api). Run only after Step 1 passed checkpoint C1, on the production instance, after setting SHA.
# The worker sends the offer-letter and certificate e-mails and draws the offer-letter PDFs, so this is the step that puts the new reportlab/svglib live.
SHA=${SHA:-PASTE_THE_40_CHARACTER_MERGE_COMMIT_HERE}
DRY_RUN=${DRY_RUN:-0}
set -euo pipefail
export LC_ALL=C
PRE_DIR=${PRE_DIR:-/opt/backups/pre-release}; ERPX_DIR=${ERPX_DIR:-/opt/erpx}   # production defaults; only overridden by the rehearsal harness

COMPOSE="docker compose -f docker-compose.prod.yml"
ENVF=$PRE_DIR/images-0107.env
run() { if [ "$DRY_RUN" = 1 ]; then echo "+ $*"; else "$@"; fi; }
q() { docker exec -i -e PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=30000" shared_postgres psql -X -U postgres -d erpx -v ON_ERROR_STOP=1 "$@"; }

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "SHA is not set; nothing was done"; exit 2; }
cd "$ERPX_DIR"
test "$(git rev-parse HEAD)" = "$SHA" || { echo "/opt/erpx is not at $SHA; run Step 1 first; nothing was done"; exit 2; }
test "$(q -tA -c 'select version_num from alembic_version' | tail -1)" = 0107 || { echo "the database is not at 0107; run Step 1 first"; exit 2; }
test -s "$ENVF" || { echo "$ENVF is missing: Step 1 did not save the rollback images; stopping"; exit 2; }
avail=$(df -B1 --output=avail / | tail -1 | tr -d ' ')
[ "$avail" -ge 3000000000 ] || { echo "less than 3 GB free; stopping"; exit 3; }

run docker builder prune -af
for svc in celery_worker celery_beat; do
  echo "== build and recreate $svc"
  run $COMPOSE build "$svc"
  run $COMPOSE up -d --no-deps "$svc"
  [ "$DRY_RUN" = 1 ] || sleep 10
  [ "$DRY_RUN" = 1 ] || echo "$svc: $(docker inspect -f '{{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' erpx_$svc)"
done
if [ "$DRY_RUN" = 1 ]; then echo "DRY RUN finished: nothing was changed"; exit 0; fi

echo "== wait for the worker to answer a ping (up to 2 minutes)"
for i in $(seq 1 24); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' erpx_celery_worker)" = healthy ] && break
  sleep 5
done
echo "== CHECKPOINT C2"
echo "worker: $(docker inspect -f '{{.State.Health.Status}}' erpx_celery_worker)"
docker exec erpx_celery_worker python -m celery -A app.core.celery_app inspect ping -t 15 2>&1 | tail -3
docker exec erpx_celery_worker python -c "import reportlab, svglib; print('reportlab', reportlab.Version, 'svglib', __import__('importlib.metadata').metadata.version('svglib'))"
echo "beat is running: $(docker inspect -f '{{.State.Status}}' erpx_celery_beat)"; docker logs --tail 6 erpx_celery_beat 2>&1 | cut -c1-200
echo "worker errors in the last 3 minutes:"; docker logs --since 3m erpx_celery_worker 2>&1 | grep -iE 'error|traceback' | head -5 || true
$COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' | head -20
echo "== STEP 2 DONE."
