#!/bin/sh
# Container entrypoint for the ERPX API image.
#
# When RUN_MIGRATIONS is truthy (set only on the service that owns schema
# management — the `api` service in compose, or a migrate Job in K8s), it applies
# Alembic migrations and runs the idempotent seed (default RBAC + bootstrap
# superadmin) BEFORE starting the app, so a fresh `docker compose up -d` yields an
# immediately usable system with no manual SQL. Every other service that shares
# this image (celery worker/beat) leaves RUN_MIGRATIONS unset and skips straight
# to its command, so migrations run exactly once and never race.
#
# Both steps are idempotent: `alembic upgrade head` is a no-op at head, and
# scripts.seed checks for existing rows before inserting.
set -e

if [ "${RUN_MIGRATIONS}" = "true" ] || [ "${RUN_MIGRATIONS}" = "1" ]; then
    echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
    alembic upgrade head
    echo "[entrypoint] Seeding RBAC + bootstrap superadmin (idempotent)..."
    python -m scripts.seed
    echo "[entrypoint] Bootstrap complete."
fi

exec "$@"
