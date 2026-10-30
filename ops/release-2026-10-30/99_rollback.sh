#!/bin/bash
# ROLLBACK. Run only if a checkpoint failed, and only the one MODE that matches. It restores the images that were running before the
# release (saved by the deploy steps in /opt/backups/pre-release/images-api.env). It never deletes data, backups or the saved dump.
#   MODE=web      put the previous web image back.
#   MODE=workers  put the previous celery_worker and celery_beat images back.
#   MODE=api      downgrade the database 0096 -> 0095 FIRST (drops only storage_trash and storage_deletion_log; any file already in
#                 Trash stays in the bucket under .trash/), then put the previous api image back. An image older than the Storage
#                 Manager cannot start while the database is at 0096, so the order matters.
#   MODE=host     restore the previous off-server backup script/config and disable the new monitor timer (no application effect).
# The full database dump taken before the migration stays in /opt/backups/pre-release/ and is a last resort that needs its own approval.
MODE=PASTE_ONE_OF_web_workers_api_host
set -euo pipefail
cd /opt/erpx
COMPOSE="docker compose -f docker-compose.prod.yml"
ENVF=/opt/backups/pre-release/images-api.env
load() { grep -E "^$1=" "$ENVF" | tail -1 | cut -d= -f2-; }
swap() {  # swap <service> <container> <name-key> <id-key>
  local name id; name=$(load "$3"); id=$(load "$4")
  [ -n "$name" ] && [ -n "$id" ] || { echo "no saved image for $1 in $ENVF"; exit 2; }
  docker image inspect "$id" > /dev/null
  docker tag "$id" "$name"
  $COMPOSE up -d --no-deps --no-build "$1"
  echo "$1 restored to $id"
}
case "$MODE" in
  web)     swap web erpx_web web_NAME web_OLD_ID ;;
  workers) swap celery_worker erpx_celery_worker celery_worker_NAME celery_worker_OLD_ID
           swap celery_beat erpx_celery_beat celery_beat_NAME celery_beat_OLD_ID ;;
  api)     if docker exec erpx_api alembic current 2>/dev/null | grep -q '^0096'; then
             docker exec erpx_api alembic downgrade 0095
           else
             echo "api is not running at 0096; checking the database directly"
             cur=$(docker exec shared_postgres psql -U postgres -d erpx -tA -c "select version_num from alembic_version")
             echo "database version: $cur"
             if [ "$cur" = "0096" ]; then echo "database is at 0096 but the api cannot downgrade it; use the new api image once for: alembic downgrade 0095"; exit 5; fi
           fi
           swap api erpx_api API_NAME API_OLD_ID
           echo "database version now: $(docker exec shared_postgres psql -U postgres -d erpx -tA -c 'select version_num from alembic_version')" ;;
  host)    PRE=$(cat /opt/backups/pre-release-host-dir.txt); D=/opt/backups/offsite
           systemctl disable --now offsite-monitor.timer || true
           for f in "$PRE"/*.sh "$PRE"/*.py "$PRE"/*.sql; do [ -f "$f" ] && install -m "$([ "${f##*.}" = sh ] && echo 755 || echo 644)" "$f" "$D/$(basename "$f")"; done
           systemctl daemon-reload; echo "host files restored from $PRE" ;;
  *)       echo "set MODE to web, workers, api or host"; exit 2 ;;
esac
$COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' | head -20
echo "== ROLLBACK ($MODE) DONE. Check /api/v1/health and the site before doing anything else."
