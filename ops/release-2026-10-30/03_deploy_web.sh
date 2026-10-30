#!/bin/bash
# STEP 3: build and recreate ONLY the web container (Storage Manager screens). The student, trainer and employee portals are not rebuilt.
# Run only after Step 2a passed C1 (the API must have the Storage Manager endpoints first), on i-0054474b85332980a, after setting SHA.
SHA=PASTE_THE_40_CHARACTER_MERGE_COMMIT_HERE
set -euo pipefail

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "SHA is not set; nothing was done"; exit 2; }
cd /opt/erpx
COMPOSE="docker compose -f docker-compose.prod.yml"
test "$(git rev-parse HEAD)" = "$SHA" || { echo "/opt/erpx is not at $SHA; nothing was done"; exit 2; }
test "$(docker exec erpx_api alembic current 2>&1 | tail -1 | cut -c1-4)" = 0096 || { echo "api is not at 0096; run Step 2a first"; exit 2; }
avail=$(df -B1 --output=avail / | tail -1 | tr -d ' ')
[ "$avail" -ge 3000000000 ] || { echo "less than 3 GB free; stopping"; exit 3; }

TS=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p /opt/backups/pre-release
old=$(docker inspect -f '{{.Image}}' erpx_web); name=$(docker inspect -f '{{.Config.Image}}' erpx_web)
docker tag "$old" "erpx-rollback/web:pre-release-$TS"
printf 'web_NAME=%s\nweb_OLD_ID=%s\n' "$name" "$old" >> /opt/backups/pre-release/images-api.env
echo "previous web image $old saved"

docker builder prune -af > /dev/null
$COMPOSE build web
$COMPOSE up -d --no-deps web

echo "== wait for healthy (up to 2 minutes)"
for i in $(seq 1 24); do
  st=$(docker inspect -f '{{.State.Health.Status}}' erpx_web 2>/dev/null || echo none)
  [ "$st" = healthy ] && break
  sleep 5
done
echo "web health: $st"
[ "$st" = healthy ] || { echo "!! web not healthy. Rollback: 99_rollback.sh with MODE=web"; docker logs --tail 20 erpx_web 2>&1; exit 4; }

echo "== CHECKPOINT C3"
echo "new bundle contains the Storage Manager: $(docker exec erpx_web sh -c 'grep -rl "Storage Manager" /usr/share/nginx/html 2>/dev/null | head -1')"
echo "site answers: $(docker exec erpx_web wget -q -O - http://localhost/ | head -c 80)"
$COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' | head -20
echo "== STEP 3 DONE. Now do the production acceptance checklist in docs/storage-manager.md (as a plain Administrator, then a superuser)."
