#!/bin/bash
# ROLLBACK (internship onboarding, PR #161). Run only if a checkpoint failed, and only the one MODE that matches. It restores the images that were running before the
# release (saved by the deploy steps in /opt/backups/pre-release/images-0100.env). It never deletes data, backups or the saved dump.
#   MODE=web      put the previous web image back.
#   MODE=workers  put the previous celery_worker and celery_beat images back.
#   MODE=api      downgrade the database 0100 -> 0097 FIRST (drops only the internship onboarding tables: settings, templates,
#                 applications, documents, events, payment orders/ledger/notifications, receipts; bulk_export_jobs and the
#                 Storage Manager tables stay). Uploaded onboarding files and receipts stay in the bucket under onboarding/.
#                 Export the payment ledger (payments.csv) BEFORE rolling back if any real payment was taken. Then put the
#                 previous api image back. An image older than 0100 cannot start while the database is at 0100.
# The full database dump taken before the migration stays in /opt/backups/pre-release/ and is a last resort that needs its own approval.
MODE=PASTE_ONE_OF_web_workers_api
set -euo pipefail
cd /opt/erpx
COMPOSE="docker compose -f docker-compose.prod.yml"
ENVF=/opt/backups/pre-release/images-0100.env
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
  api)     if docker exec erpx_api alembic current 2>/dev/null | grep -q '^0100'; then
             docker exec erpx_api alembic downgrade 0097
           else
             echo "api is not running at 0100; checking the database directly"
             cur=$(docker exec shared_postgres psql -U postgres -d erpx -tA -c "select version_num from alembic_version")
             echo "database version: $cur"
             if [ "$cur" = "0100" ]; then echo "database is at 0100 but the api cannot downgrade it; use the new api image once for: alembic downgrade 0097"; exit 5; fi
           fi
           swap api erpx_api API_NAME API_OLD_ID
           echo "database version now: $(docker exec shared_postgres psql -U postgres -d erpx -tA -c 'select version_num from alembic_version')" ;;
  *)       echo "set MODE to web, workers or api"; exit 2 ;;
esac
$COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' | head -20
echo "== ROLLBACK ($MODE) DONE. Check /api/v1/health and the site before doing anything else."
