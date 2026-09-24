#!/bin/bash
# Run on the instance (via `aws ssm send-command`, see README.md) to deploy
# the latest default-branch commit of both apps. Idempotent — safe to run
# any time, including when nothing has changed.
set -euo pipefail

echo "== ERPX =="
cd /opt/erpx
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build

echo "== Pentrix-share =="
cd /opt/pentrix
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build

echo "== pruning old images =="
docker image prune -f

echo "== done =="
docker ps --format "table {{.Names}}\t{{.Status}}"
