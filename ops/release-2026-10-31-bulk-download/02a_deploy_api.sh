#!/bin/bash
# STEP 2a (bulk download release, PR #159): build and recreate ONLY the api container. Starting it applies migration 0097 (alembic upgrade head)
# and the RBAC seed. Worker, beat, web, MinIO, Postgres, Redis, Caddy and Pentrix are not touched.
# Before anything changes it saves (a) a compressed dump of the erpx database and (b) the running image id, so
# 99_rollback.sh has real targets. If a check fails the script stops and prints what to do; it never rolls back by itself.
# Run only after Step 1, on i-0054474b85332980a, after setting SHA.
SHA=PASTE_THE_40_CHARACTER_MERGE_COMMIT_HERE
set -euo pipefail
# Never overlap the backups: the in-app dump runs at 02:00 UTC and the off-server backup at 03:30 UTC.
h=$(date -u +%H%M); if [ "$h" -ge 0145 ] && [ "$h" -le 0430 ]; then echo "inside the 01:45-04:30 UTC backup window; run later"; exit 3; fi

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "SHA is not set; nothing was done"; exit 2; }
cd /opt/erpx
COMPOSE="docker compose -f docker-compose.prod.yml"
test "$(git rev-parse HEAD)" = "$SHA" || { echo "/opt/erpx is not at $SHA (run Step 1 first); nothing was done"; exit 2; }

avail=$(df -B1 --output=avail / | tail -1 | tr -d ' ')
echo "free disk: $((avail/1024/1024)) MiB"
[ "$avail" -ge 4000000000 ] || { echo "less than 4 GB free; stopping before any build"; exit 3; }
[ "$(docker inspect -f '{{.State.Health.Status}}' erpx_api)" = healthy ] || { echo "erpx_api is not healthy before the release; stopping"; exit 3; }
echo "alembic before: $(docker exec erpx_api alembic current 2>&1 | tail -1)"
test "$(docker exec erpx_api alembic current 2>&1 | tail -1 | cut -c1-4)" = 0096 || { echo "production is not at 0096; stopping"; exit 2; }

TS=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p /opt/backups/pre-release
echo "== rollback target: the running api image"
API_NAME=$(docker inspect -f '{{.Config.Image}}' erpx_api)
API_OLD_ID=$(docker inspect -f '{{.Image}}' erpx_api)
docker tag "$API_OLD_ID" "erpx-rollback/api:pre-release-$TS"
printf 'API_NAME=%s\nAPI_OLD_ID=%s\nTS=%s\nSHA=%s\n' "$API_NAME" "$API_OLD_ID" "$TS" "$SHA" > /opt/backups/pre-release/images-0097.env
cat /opt/backups/pre-release/images-0097.env

echo "== pre-migration dump of the erpx database (custom format, compressed)"
DUMP=/opt/backups/pre-release/erpx-before-0097-$TS.dump
docker exec shared_postgres pg_dump -U postgres -d erpx -Fc -Z 6 > "$DUMP"
test -s "$DUMP"
docker exec -i shared_postgres pg_restore --list < "$DUMP" | sed -n '1,3p'   # sed reads everything: head would break the pipe under pipefail
ls -l "$DUMP"; sha256sum "$DUMP" | tee "$DUMP.sha256"

echo "== build (build cache only is cleared first, as in every earlier deploy; images and volumes are never pruned)"
docker builder prune -af > /dev/null
$COMPOSE build api
echo "== recreate api only (applies migration 0097)"
$COMPOSE up -d --no-deps api

echo "== wait for healthy (up to 4 minutes)"
for i in $(seq 1 48); do
  st=$(docker inspect -f '{{.State.Health.Status}}' erpx_api 2>/dev/null || echo none)
  [ "$st" = healthy ] && break
  sleep 5
done
echo "api health: $st"
if [ "$st" != healthy ]; then
  echo "!! api did not become healthy. Logs:"; docker logs --tail 40 erpx_api 2>&1
  echo "!! Do NOT start anything else. Rollback: run 99_rollback.sh with MODE=api (it downgrades 0097 -> 0096 first if the migration ran)."
  exit 4
fi

echo "== CHECKPOINT C1"
echo "alembic: $(docker exec erpx_api alembic current 2>&1 | tail -1)   (expect 0097 (head))"
docker exec erpx_api python -c "import urllib.request;print('health:',urllib.request.urlopen('http://localhost:8000/api/v1/health').read().decode()[:120])"
docker exec erpx_api python -c "from app.core.config import settings as s; print('BACKUP_FORMAT', s.BACKUP_FORMAT, 'BACKUP_IN_APP_SCHEDULE_ENABLED', s.BACKUP_IN_APP_SCHEDULE_ENABLED)"
docker exec shared_postgres psql -U postgres -d erpx -tA -c "select 'bulk_export_jobs table: ' || count(*) from information_schema.tables where table_name='bulk_export_jobs'"
docker exec shared_postgres psql -U postgres -d erpx -tA -c "select 'storage tables kept: ' || count(*) from information_schema.tables where table_name in ('storage_trash','storage_deletion_log')"
docker exec erpx_api python -c "from app.core.config import settings as s; print('bulk export: retention', s.BULK_EXPORT_RETENTION_HOURS, 'h, max items', s.BULK_EXPORT_MAX_ITEMS, ', max seconds', s.BULK_EXPORT_MAX_SECONDS)"
$COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' | head -20
echo "api logs (errors in the last 3 minutes):"; docker logs --since 3m erpx_api 2>&1 | grep -iE 'error|traceback' | head -5 || true
echo "== STEP 2a DONE. Worker, beat and web are still on the previous version."
