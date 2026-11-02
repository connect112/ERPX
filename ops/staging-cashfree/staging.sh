#!/usr/bin/env bash
# One entry point for the isolated Cashfree SANDBOX staging stack (project "erpx-cf-staging"). See README.md.
#   init | preflight | tunnel | up | seed | verify | sandbox-tests | status | logs [service] | down | destroy
# Every command acts only on this project's containers, network, volumes and images. Never prints a secret.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$DIR/../.." && pwd)"
ENVF="$DIR/staging.env"
PROJECT="erpx-cf-staging"

getv() { awk -v k="$1" 'index($0, k "=") == 1 { v = substr($0, length(k) + 2) } END { print v }' "$ENVF"; }
setv() {  # replace or append KEY=value without printing it (portable: no sed -i)
  local tmp; tmp="$(mktemp "$DIR/.staging.env.XXXXXX")"
  awk -v k="$1" -v v="$2" 'BEGIN { done = 0 } index($0, k "=") == 1 { print k "=" v; done = 1; next } { print } END { if (!done) print k "=" v }' "$ENVF" > "$tmp"
  mv "$tmp" "$ENVF"; chmod 600 "$ENVF"
}
dc() { docker compose --project-directory "$DIR" -f "$DIR/compose.yml" --env-file "$ENVF" "$@"; }
port() { getv STAGING_HTTP_PORT; }
need_env() { [ -f "$ENVF" ] || { echo "staging.env is missing: run ./staging.sh init"; exit 1; }; }

wait_ready() {
  echo "waiting for the API (migrations and seeding run on first start; the first build takes several minutes)..."
  for _ in $(seq 1 120); do
    if curl -fsS -o /dev/null "http://127.0.0.1:$(port)/api/v1/health/ready" 2>/dev/null; then echo "ready."; return 0; fi
    sleep 5
  done
  echo "the API did not become ready in 10 minutes: ./staging.sh logs api"; return 1
}

case "${1:-help}" in
  init)
    if [ -f "$ENVF" ]; then echo "staging.env already exists (left unchanged)."; exit 0; fi
    umask 077
    cp "$DIR/staging.env.example" "$ENVF"
    setv POSTGRES_PASSWORD "$(openssl rand -hex 24)"
    setv MINIO_ROOT_PASSWORD "$(openssl rand -hex 24)"
    setv JWT_SECRET_KEY "$(openssl rand -hex 32)"
    setv SEED_SUPERADMIN_PASSWORD "Sa-$(openssl rand -hex 16)"
    setv STAGING_ADMIN_PASSWORD "Ad-$(openssl rand -hex 16)"
    echo "created ops/staging-cashfree/staging.env (mode 600, git-ignored) with fresh staging-only secrets."
    echo "next: open it in a text editor and fill CASHFREE_APP_ID and CASHFREE_SECRET_KEY with your Cashfree TEST-mode keys."
    ;;
  preflight)
    bash "$DIR/preflight.sh" "${2:-}"
    ;;
  tunnel)
    need_env
    bash "$DIR/preflight.sh" --before-tunnel
    dc --profile tunnel up -d tunnel
    url=""
    for _ in $(seq 1 30); do
      url="$(dc --profile tunnel logs tunnel 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || true)"
      [ -n "$url" ] && break
      sleep 2
    done
    [ -n "$url" ] || { echo "no tunnel address yet: ./staging.sh logs tunnel"; exit 1; }
    setv STAGING_PUBLIC_URL "$url"
    echo "public address: $url"
    echo "Cashfree webhook URL (Test mode > Developers > Webhooks): $url/api/v1/public/payments/cashfree/webhook"
    echo "next: ./staging.sh up"
    ;;
  up)
    need_env
    bash "$DIR/preflight.sh"
    dc up -d --build
    wait_ready
    dc exec -T api python /app/staging_seed_synthetic.py bucket
    echo "local:  http://127.0.0.1:$(port)    mail viewer: http://127.0.0.1:$(getv STAGING_MAIL_PORT)"
    echo "public: $(getv STAGING_PUBLIC_URL)"
    ;;
  seed)
    need_env
    # exported in a subshell and passed by name, so the password never appears on a command line
    ( STAGING_ADMIN_EMAIL="$(getv STAGING_ADMIN_EMAIL)"; STAGING_ADMIN_PASSWORD="$(getv STAGING_ADMIN_PASSWORD)"
      export STAGING_ADMIN_EMAIL STAGING_ADMIN_PASSWORD
      dc exec -T -e STAGING_ADMIN_EMAIL -e STAGING_ADMIN_PASSWORD api python /app/staging_seed_synthetic.py seed )
    echo "sign in at $(getv STAGING_PUBLIC_URL) as $(getv STAGING_ADMIN_EMAIL) (password: STAGING_ADMIN_PASSWORD in staging.env)."
    ;;
  verify)
    need_env
    echo "== from this computer"
    curl -fsS -o /dev/null "http://127.0.0.1:$(port)/api/v1/health" && echo "OK    http://127.0.0.1:$(port) -> API" || echo "FAIL  local gateway"
    bad="$(docker ps --filter "label=com.docker.compose.project=$PROJECT" --format '{{.Names}} {{.Ports}}' | grep -E '0\.0\.0\.0:|:::|\[::\]:' || true)"
    [ -z "$bad" ] && echo "OK    every published port is on 127.0.0.1" || echo "FAIL  ports open beyond this computer: $bad"
    url="$(getv STAGING_PUBLIC_URL)"
    if [ -n "$url" ]; then
      curl -fsS -o /dev/null "$url/api/v1/health" && echo "OK    $url -> API" || echo "FAIL  public address does not reach the API"
      code="$(curl -s -o /dev/null -w '%{http_code}' "$url/api/docs")"; [ "$code" = 404 ] && echo "OK    API docs hidden through the tunnel" || echo "FAIL  /api/docs answered $code through the tunnel"
      code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$url/api/v1/public/payments/cashfree/webhook" -d '{}')"
      case "$code" in 400|401) echo "OK    webhook reachable through the tunnel and refusing unsigned calls ($code)" ;; *) echo "FAIL  webhook answered $code" ;; esac
    fi
    echo "== inside the stack"
    ( STAGING_ADMIN_EMAIL="$(getv STAGING_ADMIN_EMAIL)"; STAGING_ADMIN_PASSWORD="$(getv STAGING_ADMIN_PASSWORD)"
      export STAGING_ADMIN_EMAIL STAGING_ADMIN_PASSWORD
      dc exec -T -e STAGING_ADMIN_EMAIL -e STAGING_ADMIN_PASSWORD api python /app/staging_seed_synthetic.py verify )
    ;;
  sandbox-tests)
    need_env
    # the adapter against the real Cashfree sandbox (test money only); optional: PAID_ORDER=<order id> REFUND=1
    dc run --rm --no-deps --entrypoint python \
      -e CASHFREE_SANDBOX_TESTS=1 -e CASHFREE_SANDBOX_PAID_ORDER_ID="${PAID_ORDER:-}" -e CASHFREE_SANDBOX_REFUND="${REFUND:-}" \
      -v "$REPO/tests:/app/tests:ro" -v "$REPO/pytest.ini:/app/pytest.ini:ro" \
      api -m pytest tests/sandbox -q -p no:cacheprovider
    ;;
  status)
    need_env
    dc --profile tunnel ps
    echo "public: $(getv STAGING_PUBLIC_URL)"
    ;;
  logs)
    need_env
    dc --profile tunnel logs --tail=150 ${2:+"$2"}
    ;;
  down)
    need_env
    dc --profile tunnel stop
    echo "stopped (data kept). The tunnel address stops working; ./staging.sh tunnel gives a new one next time."
    ;;
  destroy)
    need_env
    echo "This deletes the erpx-cf-staging containers, network, volumes (its database, Redis and MinIO data) and its two"
    echo "locally built images. Nothing else on this computer is touched."
    printf 'Type %s to continue: ' "$PROJECT"; read -r answer
    [ "$answer" = "$PROJECT" ] || { echo "cancelled"; exit 1; }
    dc --profile tunnel down --volumes --remove-orphans
    docker image rm "$PROJECT/api:local" "$PROJECT/web:local" 2>/dev/null || true
    echo "removed. Delete ops/staging-cashfree/staging.env yourself if you are done, and remove the webhook in the Cashfree dashboard."
    ;;
  *)
    sed -n '2,4p' "$0"
    ;;
esac
