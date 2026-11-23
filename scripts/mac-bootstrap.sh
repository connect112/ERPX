#!/usr/bin/env bash
# ERPX local development bootstrap for macOS (Apple Silicon or Intel) and Linux.   See MACBOOK_HANDOFF.md.
#
#   bash scripts/mac-bootstrap.sh check       tool versions (Docker running, Node >= 20, Python 3.12, git)
#   bash scripts/mac-bootstrap.sh env         create .env from .env.example with a random local JWT secret (never overwrites an existing .env)
#   bash scripts/mac-bootstrap.sh up          build + start PostgreSQL, Redis, MinIO, the API (applies ALL migrations + seeds the local admin), Celery worker + beat
#   bash scripts/mac-bootstrap.sh seed        load the synthetic Learning/Internship demo data (fake people; no real student, payment or employee data)
#   bash scripts/mac-bootstrap.sh frontends   npm ci + start the five Vite dev servers in the background (logs/pids in $TMPDIR/erpx-dev)
#   bash scripts/mac-bootstrap.sh health      check the API and every frontend answers
#   bash scripts/mac-bootstrap.sh test        Python 3.12 venv (.venv), a scratch erpx_test database migrated to head, then a representative pytest run
#   bash scripts/mac-bootstrap.sh stop        stop the frontends and the containers (data volumes are kept)
#   bash scripts/mac-bootstrap.sh all         check, env, up, seed, frontends, health
#
# Safe by construction: it only talks to containers it starts on this machine; it never reads or needs production credentials; it never prints a secret.
# Works with the macOS default bash 3.2 (no associative arrays / mapfile).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)

# docker-compose.override.yml (tracked) remaps Postgres to host port 5434 for one Windows machine that already ran a native PostgreSQL. Pinning COMPOSE_FILE
# makes `docker compose` ignore the auto-loaded override, so Postgres is on the normal 5432 here. Nothing in the repo is edited.
export COMPOSE_FILE=docker-compose.yml
DEV_DIR="${TMPDIR:-/tmp}/erpx-dev"; DEV_DIR="${DEV_DIR%/}"
INFRA_AND_API="postgres redis minio api celery_worker celery_beat"
# name:directory:port   (trainer-portal is moved to 5177: its vite.config.ts and employee-portal's both default to 5175)
FRONTENDS="web:apps/web:5173 student:apps/student-portal:5174 employee:apps/employee-portal:5175 corporate:apps/corporate-portal:5176 trainer:apps/trainer-portal:5177"

say() { printf '\n==> %s\n' "$*"; }
ok()  { printf '    [ok]  %s\n' "$*"; }
bad() { printf '    [!!]  %s\n' "$*"; }
need() { command -v "$1" > /dev/null 2>&1 || { bad "$1 not found: $2"; return 1; }; }

cmd_check() {
  say "tools"; local fail=0
  need git "install Xcode command line tools: xcode-select --install" || fail=1
  need docker "install Docker Desktop for Mac (Apple silicon) and start it" || fail=1
  if command -v docker > /dev/null 2>&1; then
    docker info > /dev/null 2>&1 && ok "Docker is running ($(docker version -f '{{.Server.Os}}/{{.Server.Arch}} {{.Server.Version}}' 2>/dev/null))" || { bad "Docker is installed but not running: open Docker Desktop"; fail=1; }
    docker compose version > /dev/null 2>&1 && ok "$(docker compose version)" || { bad "docker compose plugin missing"; fail=1; }
  fi
  if need node "brew install node@20 (or nvm install 20)"; then
    local major; major=$(node -p 'process.versions.node.split(".")[0]')
    [ "$major" -ge 20 ] && ok "node $(node -v) (CI uses 20; 20 or 22 both work)" || { bad "node $(node -v): need >= 20"; fail=1; }
    need npm "comes with node" || fail=1
  else fail=1; fi
  local py=""
  for c in python3.12 python3; do command -v $c > /dev/null 2>&1 && "$c" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' 2>/dev/null && { py=$c; break; }; done
  [ -n "$py" ] && ok "python 3.12 -> $py (only needed for 'test'; the app itself runs in Docker)" || bad "python 3.12 not found: brew install python@3.12 (only needed for 'test')"
  command -v pg_dump > /dev/null 2>&1 && ok "$(pg_dump --version) (the backup tests need a PostgreSQL 16 client: brew install postgresql@16)" || bad "pg_dump missing: brew install postgresql@16 (without it ~14 backup/restore tests fail or skip; the app is unaffected)"
  [ "$fail" = 0 ] && ok "required tools present" || { bad "fix the items above, then run again"; return 1; }
  [ "$(uname -m)" = arm64 ] && ok "Apple silicon (arm64): every image used here has an arm64 build; no emulation is needed" || true
}

cmd_env() {
  say ".env"
  if [ -f .env ]; then ok ".env already exists: left untouched"; return 0; fi
  cp .env.example .env
  local secret; secret=$(openssl rand -hex 32)
  # local-only values; the JWT secret is random and never printed. sed -i differs between macOS and Linux, so write a new file instead.
  sed -e "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$secret|" \
      -e 's|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=erpx_secret|' \
      -e 's|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://erpx:erpx_secret@postgres:5432/erpx|' .env.example > .env
  chmod 600 .env
  ok ".env created from .env.example (random local JWT secret, local-only database password). Real SMTP / Cashfree / AI keys are NOT in it: add yours by hand if you need them."
}

wait_for() { # url seconds
  local i; for i in $(seq 1 "$2"); do curl -fsS -o /dev/null "$1" 2>/dev/null && return 0; sleep 2; done; return 1
}

cmd_up() {
  say "build and start PostgreSQL, Redis, MinIO, API, Celery worker + beat (first build takes several minutes)"
  [ -f .env ] || cmd_env
  docker compose up -d --build $INFRA_AND_API
  say "waiting for the API (it applies every Alembic migration, then seeds roles and the local admin, before it listens)"
  if wait_for http://localhost:8000/api/v1/health 120; then ok "API healthy: http://localhost:8000/api/v1/health"; else bad "API did not become healthy in 4 minutes"; docker compose logs --tail 40 api; return 1; fi
  ok "database revision: $(docker compose exec -T postgres psql -U erpx -d erpx -tAc 'select version_num from alembic_version' | tr -d '\r')"
  ok "local admin: admin@erpx.example.com / Admin@12345 (the compose default; local only)"
}

cmd_seed() {
  say "synthetic demo data (fake internship cohort, instructors, students; no real data)"
  docker compose exec -T api python -m scripts.seed_learning_e2e | tail -5
}

cmd_frontends() {
  say "frontends (npm ci, then Vite dev servers in the background)"
  mkdir -p "$DEV_DIR"
  local spec name dir port
  for spec in $FRONTENDS; do
    name=${spec%%:*}; dir=${spec#*:}; port=${dir##*:}; dir=${dir%:*}
    if curl -fsS -o /dev/null "http://localhost:$port" 2>/dev/null; then ok "$name already answers on :$port"; continue; fi
    [ -d "$dir/node_modules" ] || (cd "$dir" && npm ci --no-audit --no-fund > "$DEV_DIR/$name-npm.log" 2>&1) || { bad "$name: npm ci failed (see $DEV_DIR/$name-npm.log)"; return 1; }
    (cd "$dir" && nohup npm run dev -- --host 127.0.0.1 --port "$port" --strictPort > "$DEV_DIR/$name.log" 2>&1 & echo $! > "$DEV_DIR/$name.pid")
    ok "$name starting on http://localhost:$port (log: $DEV_DIR/$name.log)"
  done
}

cmd_health() {
  say "health"; local fail=0 spec name dir port
  curl -fsS http://localhost:8000/api/v1/health > /dev/null 2>&1 && ok "api   :8000" || { bad "api   :8000"; fail=1; }
  for spec in $FRONTENDS; do
    name=${spec%%:*}; dir=${spec#*:}; port=${dir##*:}
    wait_for "http://localhost:$port" 15 && ok "$name :$port" || { bad "$name :$port (see $DEV_DIR/$name.log)"; fail=1; }
  done
  docker compose ps --format 'table {{.Name}}\t{{.Status}}' 2>/dev/null | sed 's/^/    /' || true
  return $fail
}

cmd_test() {
  say "tests: Python 3.12 venv, scratch database erpx_test at head, then a representative run (the CI job runs everything: pytest -v)"
  local py=""; for c in python3.12 python3; do command -v $c > /dev/null 2>&1 && "$c" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' 2>/dev/null && { py=$c; break; }; done
  [ -n "$py" ] || { bad "python 3.12 is required for the tests: brew install python@3.12"; return 1; }
  [ -d .venv ] || "$py" -m venv .venv
  .venv/bin/pip install -q --upgrade pip && .venv/bin/pip install -q -r apps/api/requirements.txt
  docker compose up -d postgres redis minio
  docker compose exec -T postgres psql -U erpx -d postgres -qc "DROP DATABASE IF EXISTS erpx_test" -c "CREATE DATABASE erpx_test"
  export PATH="$ROOT/.venv/bin:$PATH"   # tests and their subprocesses that say "python" get the venv interpreter (macOS has no bare python)
  export DATABASE_URL=postgresql+asyncpg://erpx:erpx_secret@localhost:5432/erpx_test REDIS_URL=redis://localhost:6379/0
  export JWT_SECRET_KEY=test_secret_key_at_least_32_characters_long ENVIRONMENT=test PYTHONPATH="$ROOT"
  export MINIO_ENDPOINT=127.0.0.1:9000 MINIO_SECURE=false MINIO_BUCKET=erpx-ci-tests
  export MINIO_ACCESS_KEY MINIO_SECRET_KEY
  MINIO_ACCESS_KEY=$(grep -E '^MINIO_ROOT_USER=' .env | cut -d= -f2-); MINIO_SECRET_KEY=$(grep -E '^MINIO_ROOT_PASSWORD=' .env | cut -d= -f2-)
  (cd apps/api && ../../.venv/bin/python -m alembic upgrade head | tail -1)
  .venv/bin/python - <<'PY'
import os
from minio import Minio
c = Minio(os.environ["MINIO_ENDPOINT"], access_key=os.environ["MINIO_ACCESS_KEY"], secret_key=os.environ["MINIO_SECRET_KEY"], secure=False)
b = os.environ["MINIO_BUCKET"]
if not c.bucket_exists(b):
    c.make_bucket(b)
print("bucket", b, "ready")
PY
  .venv/bin/python -m pytest tests/unit tests/api/test_rollback_results_guard.py tests/api/test_rollback_progress_guard.py tests/api/test_learning_preflight.py -q -p no:cacheprovider
  say "frontend checks (web app): typecheck + eslint + unit tests"
  (cd apps/web && { [ -d node_modules ] || npm ci --no-audit --no-fund > /dev/null; } && npx tsc -b && npx eslint src && npx vitest run 2>&1 | tail -5)
}

cmd_stop() {
  say "stop"
  local f; for f in "$DEV_DIR"/*.pid; do [ -f "$f" ] || continue; kill "$(cat "$f")" 2>/dev/null || true; rm -f "$f"; done
  docker compose stop $INFRA_AND_API > /dev/null && ok "containers stopped (volumes and data kept; 'docker compose down -v' would delete the data)"
}

case "${1:-}" in
  check) cmd_check ;; env) cmd_env ;; up) cmd_up ;; seed) cmd_seed ;; frontends) cmd_frontends ;; health) cmd_health ;; test) cmd_test ;; stop) cmd_stop ;;
  all) cmd_check; cmd_env; cmd_up; cmd_seed; cmd_frontends; cmd_health ;;
  *) sed -n 2,14p "$0"; exit 2 ;;
esac
