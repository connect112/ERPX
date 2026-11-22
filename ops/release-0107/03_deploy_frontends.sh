#!/bin/bash
# ERPX release 0107 (PR #180)  --  STEP 3: build and recreate the three frontends this PR changed: web (admin), student_portal, trainer_portal.
# employee_portal is unchanged and is not rebuilt. Run only after Step 2 passed checkpoint C2, on the production instance, after setting SHA.
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
test "$(git rev-parse HEAD)" = "$SHA" || { echo "/opt/erpx is not at $SHA; nothing was done"; exit 2; }
test "$(q -tA -c 'select version_num from alembic_version' | tail -1)" = 0107 || { echo "the database is not at 0107; run Step 1 first"; exit 2; }
test -s "$ENVF" || { echo "$ENVF is missing: Step 1 did not save the rollback images; stopping"; exit 2; }
avail=$(df -B1 --output=avail / | tail -1 | tr -d ' ')
[ "$avail" -ge 3000000000 ] || { echo "less than 3 GB free; stopping"; exit 3; }

run docker builder prune -af
for svc in web student_portal trainer_portal; do
  echo "== build and recreate $svc"
  run $COMPOSE build "$svc"
  run $COMPOSE up -d --no-deps "$svc"
done
if [ "$DRY_RUN" = 1 ]; then echo "DRY RUN finished: nothing was changed"; exit 0; fi

echo "== wait for the containers (up to 2 minutes)"
for i in $(seq 1 24); do
  ok=1; for c in erpx_web erpx_student_portal erpx_trainer_portal; do [ "$(docker inspect -f '{{.State.Status}}' $c)" = running ] || ok=0; done
  [ "$ok" = 1 ] && break; sleep 5
done
echo "== CHECKPOINT C3"
for c in erpx_web erpx_student_portal erpx_trainer_portal; do
  echo "$c: $(docker inspect -f '{{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $c)  answers: $(docker exec $c wget -q -O - http://localhost/ | head -c 60 | tr -d '\n')"
done
echo "the web bundle contains the Learning workspace: $(docker exec erpx_web sh -c 'grep -rl "learning-workspace" /usr/share/nginx/html 2>/dev/null | head -1')"
$COMPOSE ps --format 'table {{.Name}}\t{{.Status}}' | head -20
echo "== STEP 3 DONE. Now run 04_post_deploy_verify.sh and the manual checklist (RELEASE_CHECKLIST_0107.md, part 3)."
