#!/bin/bash
# STEP 2b (bulk download release, PR #159): build and recreate celery_worker, then celery_beat, one at a time, with the same code as the api.
# They run no migration (RUN_MIGRATIONS is only set on api). The in-app backup schedule stays ON (default); retiring it is a
# separate, later approval. Run only after Step 2a passed its checkpoint C1, on i-0054474b85332980a, after setting SHA.
SHA=PASTE_THE_40_CHARACTER_MERGE_COMMIT_HERE
set -euo pipefail
# Never overlap the backups: the in-app dump runs at 02:00 UTC and the off-server backup at 03:30 UTC.
h=$(date -u +%H%M); if [ "$h" -ge 0145 ] && [ "$h" -le 0430 ]; then echo "inside the 01:45-04:30 UTC backup window; run later"; exit 3; fi

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "SHA is not set; nothing was done"; exit 2; }
cd /opt/erpx
COMPOSE="docker compose -f docker-compose.prod.yml"
test "$(git rev-parse HEAD)" = "$SHA" || { echo "/opt/erpx is not at $SHA; nothing was done"; exit 2; }
test "$(docker exec erpx_api alembic current 2>&1 | tail -1 | cut -c1-4)" = 0097 || { echo "api is not at 0097; run Step 2a first"; exit 2; }
avail=$(df -B1 --output=avail / | tail -1 | tr -d ' ')
[ "$avail" -ge 3000000000 ] || { echo "less than 3 GB free; stopping"; exit 3; }

TS=$(date -u +%Y%m%dT%H%M%SZ)
for svc in celery_worker celery_beat; do
  c=erpx_$svc
  old=$(docker inspect -f '{{.Image}}' "$c"); name=$(docker inspect -f '{{.Config.Image}}' "$c")
  docker tag "$old" "erpx-rollback/$svc:pre-release-$TS"
  printf '%s_NAME=%s\n%s_OLD_ID=%s\n' "$svc" "$name" "$svc" "$old" >> /opt/backups/pre-release/images-0097.env
  echo "== $svc: previous image $old saved"
done

docker builder prune -af > /dev/null
for svc in celery_worker celery_beat; do
  echo "== build and recreate $svc"
  $COMPOSE build "$svc"
  $COMPOSE up -d --no-deps "$svc"
  sleep 10
  echo "$svc: $(docker inspect -f '{{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' erpx_$svc)"
done

echo "== wait for the worker to answer a ping (up to 2 minutes)"
for i in $(seq 1 24); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' erpx_celery_worker)" = healthy ] && break
  sleep 5
done

echo "== CHECKPOINT C2"
echo "worker: $(docker inspect -f '{{.State.Health.Status}}' erpx_celery_worker)"
docker exec erpx_celery_worker python -m celery -A app.core.celery_app inspect ping -t 15 2>&1 | tail -3
echo "worker knows the bulk download tasks: $(docker exec erpx_celery_worker python -m celery -A app.core.celery_app inspect registered -t 15 2>&1 | grep -c 'bulk_exports\.')  (expect 2)"
docker exec erpx_celery_beat python -c "from app.core.celery_app import celery_app as c; print('beat has bulk-exports-cleanup:', 'bulk-exports-cleanup' in c.conf.beat_schedule, '| backups-trigger-daily kept:', 'backups-trigger-daily' in c.conf.beat_schedule)"
docker exec erpx_celery_beat python -c "from app.core.config import settings as s; print('beat sees BACKUP_FORMAT', s.BACKUP_FORMAT, 'BACKUP_IN_APP_SCHEDULE_ENABLED', s.BACKUP_IN_APP_SCHEDULE_ENABLED)"
echo "beat is running: $(docker inspect -f '{{.State.Status}}' erpx_celery_beat)"; docker logs --tail 6 erpx_celery_beat 2>&1 | cut -c1-200
$COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' | head -20
echo "== STEP 2b DONE."
