#!/usr/bin/env bash
# One entry point for the isolated Cashfree SANDBOX staging stack (project "erpx-cf-staging"). See README.md.
#   init | preflight | tunnel | up | refresh-app | seed | verify | sandbox-tests | evidence | status | logs [service] | down
#   | network-check | recreate-network | destroy
# Every command acts only on this project's containers, network, volumes and images. Never prints a secret.
# The Docker network is created and removed HERE, not by Compose (it is `external` in compose.yml), so no Compose
# command can ever stop services to rebuild an occupied network.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$DIR/../.." && pwd)"
ENVF="$DIR/staging.env"
PROJECT="erpx-cf-staging"
NET="${PROJECT}_default"   # the network compose.yml declares external

getv() { awk -v k="$1" '{ sub(/\r$/, "") } index($0, k "=") == 1 { v = substr($0, length(k) + 2) } END { print v }' "$ENVF"; }
setv() {  # replace or append KEY=value without printing it (portable: no sed -i)
  local tmp; tmp="$(mktemp "$DIR/.staging.env.XXXXXX")"
  awk -v k="$1" -v v="$2" 'BEGIN { done = 0 } index($0, k "=") == 1 { print k "=" v; done = 1; next } { print } END { if (!done) print k "=" v }' "$ENVF" > "$tmp"
  mv "$tmp" "$ENVF"; chmod 600 "$ENVF"
}
dc() { docker compose --project-directory "$DIR" -f "$DIR/compose.yml" --env-file "$ENVF" "$@"; }
port() { getv STAGING_HTTP_PORT; }
# --- the staging network (outside Compose's control; see the note in compose.yml)
net_exists() { docker network inspect "$NET" >/dev/null 2>&1; }
net_subnet() { docker network inspect "$NET" --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null | awk '{ for (i = 1; i <= NF; i++) if ($i !~ /:/) { print $i; exit } }'; }
net_members() { docker network inspect "$NET" --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null; }
# Creates the network on STAGING_SUBNET when it does not exist; an existing one is used exactly as it is (never changed,
# never recreated), as long as it is on STAGING_SUBNET.
ensure_network() {
  local want have
  want="$(getv STAGING_SUBNET)"
  if net_exists; then
    have="$(net_subnet)"
    if [ -n "$want" ] && [ -n "$have" ] && [ "$have" != "$want" ]; then
      echo "the network $NET is on $have but STAGING_SUBNET is $want."
      echo "Either set STAGING_SUBNET=$have in staging.env (nothing else changes), or move the stack: ./staging.sh recreate-network"
      return 1
    fi
    return 0
  fi
  [ -n "$want" ] || { echo "STAGING_SUBNET is not set in staging.env"; return 1; }
  docker network create --driver bridge --subnet "$want" \
    --label "com.docker.compose.project=$PROJECT" --label "com.erpx.staging=sandbox" "$NET" >/dev/null
  echo "created the network $NET on $want"
}
# Removes the network only when it is this project's and nothing is attached (never disconnects anything).
remove_network() {
  net_exists || return 0
  local owner members
  owner="$(docker network inspect "$NET" --format '{{index .Labels "com.docker.compose.project"}}' 2>/dev/null)"
  [ "$owner" = "$PROJECT" ] || { echo "not removing $NET: it does not belong to project $PROJECT"; return 1; }
  members="$(net_members)"
  if [ -n "${members// /}" ]; then echo "not removing $NET: still in use by: $members"; return 1; fi
  docker network rm "$NET" >/dev/null && echo "removed the network $NET"
}
# True when compose.yml (as Compose renders it) declares the network external.
net_is_external() { dc --profile tunnel config 2>/dev/null | awk '/^networks:/ { n = 1; next } /^[A-Za-z]/ { n = 0 } n && /external: true/ { f = 1 } END { exit !f }'; }

need_env() {
  [ -f "$ENVF" ] || { echo "staging.env is missing: run ./staging.sh init"; exit 1; }
  # Windows line endings (from some editors or a paste) would end up inside the values Docker reads: drop them
  if grep -q "$(printf '\r')" "$ENVF"; then tr -d '\r' < "$ENVF" > "$ENVF.tmp" && mv "$ENVF.tmp" "$ENVF" && chmod 600 "$ENVF"; fi
}

# nginx resolves its upstream names (api, web, minio) when it loads its configuration, so a recreated container that
# got a new address is unreachable (502) until it reloads. A reload is graceful: the gateway container keeps running.
reload_gateway() { dc exec -T gateway nginx -s reload >/dev/null 2>&1 && echo "gateway reloaded (picks up the current addresses)" || echo "note: could not reload the gateway (not running yet?)"; }

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
    "${BASH:-bash}" "$DIR/preflight.sh" "${2:-}"
    ;;
  tunnel)
    need_env
    "${BASH:-bash}" "$DIR/preflight.sh" --before-tunnel
    ensure_network
    # only the tunnel container: no dependencies are started or touched, and the (external) network is never changed
    dc --profile tunnel up -d --no-deps tunnel
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
    echo "next: ./staging.sh up (first start)  or  ./staging.sh refresh-app (stack already running: only api/worker/beat restart)"
    ;;
  up)
    need_env
    "${BASH:-bash}" "$DIR/preflight.sh"
    ensure_network
    dc up -d --build
    reload_gateway
    wait_ready
    dc exec -T api python /app/staging_seed_synthetic.py bucket
    echo "local:  http://127.0.0.1:$(port)    mail viewer: http://127.0.0.1:$(getv STAGING_MAIL_PORT)"
    echo "public: $(getv STAGING_PUBLIC_URL)"
    ;;
  refresh-app)
    # After a new tunnel address: restarts ONLY api, celery_worker and celery_beat so they pick up STAGING_PUBLIC_URL
    # (FRONTEND_URL, CORS, student links, the Cashfree return URL). Postgres, Redis, MinIO, Mailpit, web, the gateway and
    # the tunnel keep running, no image is built, and the network is not touched (it is external).
    need_env
    "${BASH:-bash}" "$DIR/preflight.sh"
    ensure_network
    echo "restarting api, celery_worker, celery_beat with STAGING_PUBLIC_URL=$(getv STAGING_PUBLIC_URL)"
    dc up -d --no-deps --force-recreate api celery_worker celery_beat
    reload_gateway
    wait_ready
    echo "the API now uses FRONTEND_URL=$(dc exec -T api printenv FRONTEND_URL)"
    echo "Cashfree webhook URL: $(getv STAGING_PUBLIC_URL)/api/v1/public/payments/cashfree/webhook (must be this in the dashboard)"
    ;;
  network-check)
    # read-only: nothing is created, changed or removed
    need_env
    bad=0
    echo "network:  $NET (STAGING_SUBNET=$(getv STAGING_SUBNET))"
    if net_exists; then
      echo "exists:   yes, subnet $(net_subnet)"
      echo "attached: $(net_members)"
      [ "$(net_subnet)" = "$(getv STAGING_SUBNET)" ] && echo "OK    subnet matches STAGING_SUBNET" || { echo "FAIL  subnet differs from STAGING_SUBNET (set STAGING_SUBNET to the existing one, or ./staging.sh recreate-network)"; bad=1; }
    else
      echo "exists:   no (./staging.sh tunnel or up creates it on STAGING_SUBNET)"
    fi
    if net_is_external; then echo "OK    compose.yml declares the network external: Compose will never recreate or remove it"
    else echo "FAIL  compose.yml does not declare the network external: an up could try to rebuild it"; bad=1; fi
    exit "$bad"
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
    ensure_network
    # the adapter against the real Cashfree sandbox (test money only); optional: PAID_ORDER=<order id> REFUND=1
    dc run --rm --no-deps --entrypoint python \
      -e CASHFREE_SANDBOX_TESTS=1 -e CASHFREE_SANDBOX_PAID_ORDER_ID="${PAID_ORDER:-}" -e CASHFREE_SANDBOX_REFUND="${REFUND:-}" \
      -v "$REPO/tests:/app/tests:ro" -v "$REPO/pytest.ini:/app/pytest.ini:ro" \
      api -m pytest tests/sandbox -q -p no:cacheprovider
    ;;
  evidence)
    need_env
    # read-only snapshot of the test results: ledger, documents, notifications, checks, and every Mailpit message
    out="$DIR/evidence/$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p "$out/mail" && chmod 700 "$DIR/evidence" "$out"
    dc exec -T postgres psql -U erpx -d erpx_staging -v ON_ERROR_STOP=1 -q -f - < "$DIR/evidence.sql" > "$out/ledger.txt"
    mail="http://127.0.0.1:$(getv STAGING_MAIL_PORT)"
    curl -fsS "$mail/api/v1/messages?limit=1000" > "$out/mail/messages.json"
    for id in $(grep -oE '"ID":"[^"]+"' "$out/mail/messages.json" | cut -d'"' -f4); do
      curl -fsS "$mail/api/v1/message/$id/raw" > "$out/mail/$id.eml"
    done
    grep -oE '"Subject":"[^"]*"' "$out/mail/messages.json" | cut -d'"' -f4 | sort | uniq -c | sort -rn > "$out/mail/subjects.txt"
    echo "saved to ${out#"$REPO"/} (git-ignored)"
    echo "== checks (each must be 0)"; sed -n '/== CHECKS/,/== Cashfree/p' "$out/ledger.txt" | grep -vE '^==|^-|check \|'
    echo "== emails per subject (a receipt or credit note listed twice would mean a duplicate email)"; cat "$out/mail/subjects.txt"
    ;;
  recreate-network)
    need_env
    echo "Moves this stack onto STAGING_SUBNET: saves evidence first, then removes this project's containers and network."
    echo "(Not needed just to keep the existing subnet: set STAGING_SUBNET to it instead. Not needed for a new tunnel address: ./staging.sh refresh-app.)"
    echo "Volumes (database, Redis, MinIO, Mailpit) are kept. The tunnel gets a new address afterwards."
    printf 'Type %s to continue: ' "$PROJECT"; read -r answer
    [ "$answer" = "$PROJECT" ] || { echo "cancelled"; exit 1; }
    "$0" evidence
    dc --profile tunnel down --remove-orphans
    remove_network   # Compose leaves the external network alone; this removes it (only this project's, only if empty)
    echo "done (data kept). Next: ./staging.sh tunnel, ./staging.sh up, then update the webhook URL in the Cashfree dashboard."
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
    remove_network
    docker image rm "$PROJECT/api:local" "$PROJECT/web:local" 2>/dev/null || true
    echo "removed. Delete ops/staging-cashfree/staging.env yourself if you are done, and remove the webhook in the Cashfree dashboard."
    ;;
  *)
    sed -n '2,4p' "$0"
    ;;
esac
