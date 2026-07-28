#!/usr/bin/env bash
# One-command test runner for ERPX.
#
# Assumes the docker-compose stack is up (`docker compose up -d postgres`)
# and migrations have already been applied once (see README "Deployment"
# section). Run from the repo root:
#
#   bash scripts/run-tests.sh
#
set -euo pipefail
cd "$(dirname "$0")/.."

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
export DATABASE_URL="postgresql+asyncpg://erpx:erpx_secret@${DB_HOST}:${DB_PORT}/erpx_test"
export JWT_SECRET_KEY="test_secret_key_at_least_32_characters_long"

echo "==> Frontend: lint"
(cd apps/web && npm run lint)

echo "==> Frontend: typecheck"
(cd apps/web && npx tsc -b)

echo "==> Backend: unit + api + integration + security + performance"
python -m pytest tests/unit tests/api tests/integration tests/security tests/performance -q

echo
echo "All checks passed."
