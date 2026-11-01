#!/bin/bash
# Refuses to start the staging stack unless it is unmistakably a sandbox: run before `docker compose up`.
set -euo pipefail
ENVF="${1:-ops/staging-cashfree/staging.env}"
[ -f "$ENVF" ] || { echo "missing $ENVF (copy staging.env.example)"; exit 2; }
git check-ignore -q "$ENVF" || { echo "$ENVF is not git-ignored: do not keep secrets in a tracked file"; exit 2; }
get() { grep -E "^$1=" "$ENVF" | tail -1 | cut -d= -f2-; }
[ -n "$(get CASHFREE_APP_ID)" ] && [ -n "$(get CASHFREE_SECRET_KEY)" ] || { echo "sandbox keys not set"; exit 2; }
grep -qiE "^CASHFREE_(ENV=production|ALLOW_PRODUCTION=true)" "$ENVF" && { echo "production settings found in $ENVF"; exit 2; }
case "$(get STAGING_PUBLIC_URL)" in https://*) ;; *) echo "STAGING_PUBLIC_URL must be https://"; exit 2 ;; esac
case "$(get STAGING_PUBLIC_URL)" in *pentrix.in*) echo "STAGING_PUBLIC_URL points at a production domain"; exit 2 ;; esac
for v in POSTGRES_PASSWORD MINIO_ROOT_PASSWORD JWT_SECRET_KEY SEED_SUPERADMIN_PASSWORD; do
  [ "$(get "$v" | tr -d '\n' | wc -c)" -ge 12 ] || { echo "$v must be a fresh random value (12+ characters)"; exit 2; }
done
docker ps --format '{{.Names}}' | grep -qE '^(erpx_api|shared_postgres)$' && ! docker ps --format '{{.Names}}' | grep -q erpx_staging_mailpit \
  && { echo "an ERPX stack is already running on this machine (production?): use a separate machine"; exit 2; }
echo "preflight ok: sandbox only, separate secrets, public URL $(get STAGING_PUBLIC_URL)"
