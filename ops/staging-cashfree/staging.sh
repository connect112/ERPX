#!/usr/bin/env bash
# One entry point for the isolated Cashfree SANDBOX staging stack (project "erpx-cf-staging"). See README.md.
#   init | preflight | tunnel | up | refresh-app | seed | verify | sandbox-tests | evidence | status | logs [service] | down
#   | network-check | gate on|off|status | recon on|off|check|status|report|run | recreate-network | destroy
# Every command acts only on this project's containers, network, volumes and images. Never prints a secret.
# The Docker network is created and removed HERE, not by Compose (it is `external` in compose.yml), so no Compose
# command can ever stop services to rebuild an occupied network.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$DIR/../.." && pwd)"
ENVF="$DIR/staging.env"
PROJECT="erpx-cf-staging"
NET="${PROJECT}_default"   # the network compose.yml declares external
GATE="$DIR/gate"            # mounted into the gateway; empty unless a test needs it (see `gate`)

getv() { awk -v k="$1" '{ sub(/\r$/, "") } index($0, k "=") == 1 { v = substr($0, length(k) + 2) } END { print v }' "$ENVF"; }
setv() {  # replace or append KEY=value without printing it (portable: no sed -i)
  local tmp; tmp="$(mktemp "$DIR/.staging.env.XXXXXX")"
  awk -v k="$1" -v v="$2" 'BEGIN { done = 0 } index($0, k "=") == 1 { print k "=" v; done = 1; next } { print } END { if (!done) print k "=" v }' "$ENVF" > "$tmp"
  mv "$tmp" "$ENVF"; chmod 600 "$ENVF"
}
dc() { mkdir -p "$GATE"; docker compose --project-directory "$DIR" -f "$DIR/compose.yml" --env-file "$ENVF" "$@"; }
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

# --- the staging test modes (gate-templates/ -> gate/ -> the gateway). Staging gateway only; no application code is involved.
#   gate  (mode "manual")     webhook refused, payment return page blocked, celery_beat STOPPED: tests the student's button.
#   recon (mode "reconcile")  webhook refused, return page blocked, student status-check endpoint refused; celery_beat and
#                             celery_worker keep RUNNING: tests the scheduled reconciliation on its own.
gate_is_on() { ls "$GATE"/*.conf >/dev/null 2>&1; }
gate_mode() { cat "$GATE/mode" 2>/dev/null || true; }
gate_warn() { gate_is_on && echo "NOTE: a staging test mode is ON ($(gate_mode)): webhook refused and payment return page blocked: ./staging.sh gate off (or recon off)" || true; }
# up and refresh-app would restart containers the test depends on (the reconciliation, or its logs)
gate_refuse() { if gate_is_on; then echo "a staging test mode is ON ($(gate_mode)): finish the test and run ./staging.sh gate off (or recon off) first (this command would restart containers the test relies on)."; exit 1; fi; }
# validate the gateway configuration first; nginx keeps running the old one if the new one is invalid
gate_reload() { dc exec -T gateway nginx -t >/dev/null 2>&1 && dc exec -T gateway nginx -s reload >/dev/null 2>&1; }
svc_state() { dc ps "$1" --format '{{.State}}' 2>/dev/null | head -1; }
# The one way back, used by gate off, recon off, the rollback of a failed start and the trap of `recon run`: removes every
# gate file, makes the gateway pick that up (a reload, or a restart of the gateway alone if the reload fails; its gate
# folder is empty by then, so a restart is always a clean configuration) and makes sure Beat and the worker are running.
gate_remove_all() {
  rm -f "${GATE:?}"/*.conf "${GATE:?}/mode"
  if ! gate_reload; then
    echo "could not reload the gateway; restarting the gateway only (its gate folder is empty)"
    dc restart gateway >/dev/null 2>&1 || echo "COULD NOT RESTART THE GATEWAY: ./staging.sh logs gateway"
  fi
  dc start celery_beat celery_worker >/dev/null 2>&1 || true
  echo "restored: webhook, return page and status checks reach ERPX again; celery_beat $(svc_state celery_beat), celery_worker $(svc_state celery_worker)"
}
# installs the templates for a mode ("manual" or "reconcile"), validates, and rolls back by itself if nginx rejects them
gate_install() {
  mkdir -p "$GATE"
  cp "$DIR"/gate-templates/*.conf "$GATE"/
  if [ "$1" = reconcile ]; then cp "$DIR"/gate-templates/reconcile/*.conf "$GATE"/; fi
  date -u +%Y-%m-%dT%H:%M:%SZ > "$GATE/since"
  echo "$1" > "$GATE/mode"
  if ! gate_reload; then
    gate_remove_all >/dev/null
    echo "the gateway refused the gate configuration; the gate was removed again and nothing changed."
    return 1
  fi
}
# --- reconciliation test (recon): everything below only reads logs and the database, except recon on/off/run
gw_log() { dc logs --no-log-prefix --since "$1" gateway 2>/dev/null || true; }
count_lines() { grep -c "$1" || true; }
recon_counters() {  # <gateway log text>: what the gateway saw since the mode went on
  hook_total="$(printf '%s\n' "$1" | grep 'payments/cashfree/webhook' | count_lines '')" || true
  hook_ok="$(printf '%s\n' "$1" | grep 'payments/cashfree/webhook' | grep -v '" 503 ' | count_lines '')" || true
  ref_total="$(printf '%s\n' "$1" | grep 'payments/refresh' | count_lines '')" || true
  ref_reached="$(printf '%s\n' "$1" | grep 'payments/refresh' | grep -v '" 503 ' | count_lines '')" || true
  ret_total="$(printf '%s\n' "$1" | count_lines 'internship-onboarding?order=')" || true
}
psql_app() { dc exec -T postgres psql -U erpx -d erpx_staging -X -q "$@"; }
recon_query() {  # <application ref or ''> <since> <task_ok or ''>: the facts and checks of recon.sql, one key=value per line
  psql_app -v "app=$1" -v "since=$2" -v "task_ok=$3" -f - < "$DIR/recon.sql"
}
recon_on() {
  if gate_is_on; then echo "a staging test mode is already on ($(gate_mode)): ./staging.sh gate off (or recon off) first"; return 1; fi
  ensure_network
  for svc in celery_worker celery_beat; do
    [ "$(svc_state "$svc")" = running ] || dc start "$svc" >/dev/null 2>&1 || true
    [ "$(svc_state "$svc")" = running ] || { echo "$svc is not running: the scheduled reconciliation cannot be tested (./staging.sh up first)"; return 1; }
  done
  dc up -d --no-deps gateway   # only recreates the gateway if its definition changed (the first time after this update)
  gate_install reconcile || return 1
  echo "recon mode ON (since $(cat "$GATE/since")): webhook refused (503), payment return page blocked, student status-check endpoint refused (503)."
  echo "celery_beat and celery_worker are RUNNING and untouched. The scheduled task runs at :00, :15, :30, :45 UTC and only picks up orders older than 10 minutes."
  echo "Next: create a student, pay with testsuccess@gocash, and do NOT press any status button. Then ./staging.sh recon status, and ./staging.sh recon report <application ref>."
  echo "Turn it off afterwards: ./staging.sh recon off     (or let ./staging.sh recon run do everything and roll back by itself)"
}
recon_status() {
  if gate_is_on; then echo "mode: ON ($(gate_mode))"; else echo "mode: off"; fi
  echo "celery_beat: $(svc_state celery_beat)   celery_worker: $(svc_state celery_worker)"
  [ -f "$GATE/since" ] || { echo "the test mode has not been used yet."; return 0; }
  since="$(cat "$GATE/since")"
  recon_counters "$(gw_log "$since")"
  echo "since $since, as the gateway saw it:"
  echo "  Cashfree webhook calls: $hook_total (refused with 503: $((hook_total - hook_ok)); any other answer would invalidate the test: $hook_ok)"
  echo "  payment return-page requests blocked: $ret_total"
  echo "  student status-check calls: $ref_total (refused with 503: $((ref_total - ref_reached)); reached ERPX: $ref_reached)"
  echo "scheduled reconciliation, from the Beat and worker logs:"
  dc logs --timestamps --no-log-prefix --since "$since" celery_beat 2>/dev/null | grep 'Sending due task internship-onboarding-reconcile-payments' | awk '{ print "  beat sent the task at " $1 }' | tail -5 || true
  dc logs --timestamps --no-log-prefix --since "$since" celery_worker 2>/dev/null | grep 'reconcile_payments\[.*succeeded' | sed 's/^\([^ ]*\) .*succeeded in \([^:]*\): /  worker ran it at \1 (\2): /' | tail -5 || true
  echo "Cashfree orders created since then:"
  recon_query "" "$since" "" | grep -E '^fact\.(application|order|order_status|order_created_at|order_last_checked_at|order_paid_at)=' | sed 's/^/  /' || true
}
recon_report() {  # <application ref or ''>
  app="${1:-}"
  case "$app" in *[!A-Za-z0-9-]*) echo "the application reference may contain only letters, digits and dashes"; return 2 ;; esac
  [ -f "$GATE/since" ] || { echo "no recon test has been started (./staging.sh recon on)"; return 2; }
  since="$(cat "$GATE/since")"
  out="$DIR/evidence/recon-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$out" && chmod 700 "$DIR/evidence" "$out"
  # only the lines that matter are kept, never whole logs
  gw="$(gw_log "$since")"
  printf '%s\n' "$gw" | grep -E 'payments/cashfree/webhook|payments/refresh|internship-onboarding\?order=' > "$out/gateway-lines.txt" || true
  dc logs --timestamps --no-log-prefix --since "$since" celery_beat 2>/dev/null | grep 'Sending due task internship-onboarding-reconcile-payments' > "$out/beat-lines.txt" || true
  dc logs --timestamps --no-log-prefix --since "$since" celery_worker 2>/dev/null | grep -E 'reconcile_payments\[|sandbox.cashfree.com/pg/orders/.*/payments' > "$out/worker-lines.txt" || true
  task_ok=""; task_line=""
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      *reconcile_payments*succeeded*)
        n="$(printf '%s' "$line" | sed -n "s/.*'confirmed': \([0-9]*\).*/\1/p")"
        if [ "${n:-0}" -ge 1 ]; then ts="${line%% *}"; task_ok="${ts%%.*}Z"; task_line="$line"; fi ;;
    esac
  done < "$out/worker-lines.txt"
  recon_query "$app" "$since" "$task_ok" > "$out/facts.txt"
  recon_counters "$gw"
  beat_ticks="$(count_lines 'Sending due task' < "$out/beat-lines.txt")"
  api_lines="$(grep -c 'sandbox.cashfree.com/pg/orders/.*/payments' "$out/worker-lines.txt" || true)"
  kv() { grep "^$1=" "$out/facts.txt" | head -1 | cut -d= -f2-; }
  mails="n/a"
  if [ -n "$(kv fact.receipt_number)" ] && [ "$(kv fact.receipt_number)" != NONE ]; then
    mails="$(curl -fsS "http://127.0.0.1:$(getv STAGING_MAIL_PORT)/api/v1/messages?limit=1000" 2>/dev/null | grep -o '"Subject":"[^"]*"' | grep -c "$(kv fact.receipt_number)" || true)"
  fi
  bad_integrity="$(grep '^integrity\.' "$out/facts.txt" | grep -vc '=0$' || true)"
  fails=""
  verdict() {  # <description> <true|false>
    if [ "$2" = true ]; then echo "PASS  $1"; else echo "FAIL  $1"; fails="$fails
  - $1"; fi
  }
  {
    echo "Automatic reconciliation test: report $(date -u +%Y-%m-%dT%H:%M:%SZ)   (test mode on since $since)"
    echo "application $(kv fact.application)  order $(kv fact.order)  status $(kv fact.order_status)  Cashfree payment $(kv fact.cashfree_payment_id)"
    echo "order created $(kv fact.order_created_at)  last checked $(kv fact.order_last_checked_at)  paid $(kv fact.order_paid_at)  receipt $(kv fact.receipt_number)"
    echo "payment confirmed event at $(kv fact.confirmed_event_at), source '$(kv fact.confirmed_event_source)'"
    echo "task run that confirmed it: ${task_line:-none found}"
    echo "== isolation"
    verdict "the test mode was on before checkout started" "$(kv check.test_mode_was_on_before_checkout)"
    verdict "no Cashfree notification was accepted by the gateway ($hook_ok non-503 answers; $hook_total call(s) in all)" "$([ "$hook_ok" = 0 ] && echo true || echo false)"
    verdict "no notification reached ERPX (webhook table has no row for this order)" "$(kv check.no_notification_reached_erpx)"
    verdict "no student status check reached ERPX ($ref_reached reached; $((ref_total - ref_reached)) refused at the gateway)" "$([ "$ref_reached" = 0 ] && echo true || echo false)"
    echo "== the scheduled reconciliation did it"
    verdict "Celery Beat sent the reconciliation task ($beat_ticks time(s) since the mode went on)" "$([ "$beat_ticks" -ge 1 ] && echo true || echo false)"
    verdict "the worker ran it and it confirmed at least one payment" "$([ -n "$task_ok" ] && echo true || echo false)"
    verdict "ERPX recorded the confirmation inside that run (within 120 s of its end)" "$(kv check.confirmation_inside_scheduled_task_run)"
    verdict "confirmation came at least 10 minutes after checkout (the task's minimum order age)" "$(kv check.confirmed_at_least_10_minutes_after_checkout)"
    verdict "the confirmation's source is 'status check' and the order's last_checked_at matches it" "$([ "$(kv check.confirmation_source_is_status_check)" = true ] && [ "$(kv check.order_last_checked_at_matches_confirmation)" = true ] && echo true || echo false)"
    echo "INFO  Cashfree API request lines for an order's payments in the worker log: $api_lines (corroboration only; the confirmation itself can only come from Cashfree's answer for the exact amount)"
    echo "== result in ERPX"
    verdict "paid, with exactly one confirmed payment, one receipt and one payment_confirmed event" "$(kv check.paid_by_one_payment_one_receipt_one_event)"
    verdict "exactly one receipt email in Mailpit for $(kv fact.receipt_number) (found $mails)" "$([ "$mails" = 1 ] && echo true || echo false)"
    verdict "the five integrity checks are all 0 (duplicates, missing documents, refund mismatches, accounting entries)" "$([ "$bad_integrity" = 0 ] && echo true || echo false)"
    echo "== context"
    echo "Cashfree notifications refused at the gateway: $((hook_total - hook_ok)); payment return-page requests blocked: $ret_total; student status checks refused: $((ref_total - ref_reached))"
    if [ -z "$fails" ]; then
      echo "RESULT: every criterion is met. Record the acceptance as passed only after the owner has read this report and the files in ${out#"$REPO"/}."
    else
      echo "RESULT: NOT PROVEN. Not met:$fails"
    fi
  } > "$out/report.txt"
  cat "$out/report.txt"
  echo "saved to ${out#"$REPO"/} (git-ignored; gateway, Beat and worker lines are filtered, no secrets)"
  [ -z "$fails" ]
}
recon_rollback_trap() {  # runs when `recon run` ends in any way: success, failure, timeout, Ctrl-C, closed terminal
  rc=$?
  trap - EXIT INT TERM HUP
  set +e
  echo "== rollback"
  gate_remove_all
  exit "$rc"
}
recon_run() {  # <application ref or ''> [minutes]
  app="${1:-}"; minutes="${2:-45}"
  case "$minutes" in ''|*[!0-9]*) echo "minutes must be a number"; return 2 ;; esac
  case "$app" in *[!A-Za-z0-9-]*) echo "the application reference may contain only letters, digits and dashes"; return 2 ;; esac
  if gate_is_on; then echo "a staging test mode is already on ($(gate_mode)): ./staging.sh gate off (or recon off) first"; return 1; fi
  trap recon_rollback_trap EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  trap 'exit 129' HUP
  recon_on || return 1
  since="$(cat "$GATE/since")"
  echo "Waiting up to $minutes minutes for a Cashfree order created from now on to become paid (checking every 30 s)."
  paid=0
  for i in $(seq 1 $((minutes * 2))); do
    sleep 30
    if [ -n "$app" ]; then
      paid="$(psql_app -tA -c "SELECT count(*) FROM internship_payment_orders o JOIN internship_onboarding_applications a ON a.id = o.application_id WHERE o.method = 'cashfree' AND o.status = 'paid' AND a.reference = '$app' AND o.created_at >= '$since'" | head -1)"
    else
      paid="$(psql_app -tA -c "SELECT count(*) FROM internship_payment_orders WHERE method = 'cashfree' AND status = 'paid' AND created_at >= '$since'" | head -1)"
    fi
    [ "${paid:-0}" -ge 1 ] && break
    [ $((i % 4)) = 0 ] && echo "  ... $((i / 2)) min, not paid in ERPX yet ($(date -u +%H:%M:%S) UTC)"
  done
  if [ "${paid:-0}" -ge 1 ]; then echo "paid in ERPX."; else echo "not paid in ERPX within $minutes minutes."; fi
  recon_report "$app"
}

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
    gate_refuse
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
    gate_refuse
    "${BASH:-bash}" "$DIR/preflight.sh"
    ensure_network
    echo "restarting api, celery_worker, celery_beat with STAGING_PUBLIC_URL=$(getv STAGING_PUBLIC_URL)"
    dc up -d --no-deps --force-recreate api celery_worker celery_beat
    reload_gateway
    wait_ready
    echo "the API now uses FRONTEND_URL=$(dc exec -T api printenv FRONTEND_URL)"
    gate_warn
    echo "Cashfree webhook URL: $(getv STAGING_PUBLIC_URL)/api/v1/public/payments/cashfree/webhook (must be this in the dashboard)"
    ;;
  gate)
    # The manual status-check test: makes sure NOTHING but the student's button can confirm a payment.
    #   gate on     Cashfree's webhook answers 503; the return page (/internship-onboarding?order=...) is answered by the
    #               gateway, so the web app never loads there and never runs its automatic status check; the
    #               15-minute reconciliation (celery_beat) is stopped. The button's endpoint stays open.
    #   gate off    undoes all three.   gate status   shows what is on and which status checks the gateway has seen.
    need_env
    case "${2:-status}" in
      on)
        if gate_is_on; then echo "a staging test mode is already on ($(gate_mode)): ./staging.sh gate off (or recon off) first"; exit 1; fi
        ensure_network
        dc up -d --no-deps gateway   # only recreates the gateway if its definition changed (the first time after this update)
        gate_install manual || exit 1
        dc stop celery_beat
        echo "gate ON (since $(cat "$GATE/since")): webhook refused (503), payment return page blocked, reconciliation stopped."
        echo "Pay with a student; Cashfree shows its success page, then the browser lands on ERPX's gate page. Open the student's"
        echo "onboarding link WITHOUT ?order=, press 'I have paid: check status', then ./staging.sh gate status and ./staging.sh evidence."
        echo "Turn it off afterwards: ./staging.sh gate off"
        ;;
      off)
        gate_remove_all
        echo "gate OFF: webhook, return page and the 15-minute reconciliation work normally again (the since-time is kept for gate status)."
        ;;
      status)
        if gate_is_on; then echo "gate: ON (mode: $(gate_mode))"; else echo "gate: off"; fi
        echo "reconciliation (celery_beat): $(dc ps celery_beat --format '{{.State}}' 2>/dev/null | head -1)"
        if [ -f "$GATE/since" ]; then
          since="$(cat "$GATE/since")"
          log="$(dc logs --no-log-prefix --since "$since" gateway 2>/dev/null || true)"
          echo "since $since, as the gateway saw it:"
          echo "  webhook calls (503 = refused):     $(echo "$log" | grep -c 'payments/cashfree/webhook' || true)"
          echo "  return-page requests (?order=):    $(echo "$log" | grep -c 'internship-onboarding?order=' || true)"
          echo "  status checks (POST .../payments/refresh), each is the button or an automatic page-load check:"
          echo "$log" | grep 'payments/refresh' | awk '{ print "    " $4, $6, $7, $9 }' || true
          echo "  (with the return page blocked nothing automatic makes these calls: match the time to your button press; the log has no student identity)"
        else echo "the gate has not been used yet."; fi
        ;;
      *) echo "usage: ./staging.sh gate on|off|status"; exit 1 ;;
    esac
    ;;
  recon)
    # The automatic-reconciliation test: Cashfree's webhook, the return-page check and every student status check are out
    # of the way, and the scheduled reconciliation (Beat + worker) is left running and untouched.
    #   recon on | off | status | check | report [application ref] | run [application ref] [minutes]
    need_env
    case "${2:-status}" in
      on) recon_on || exit 1 ;;
      off) gate_remove_all; echo "recon OFF: normal webhook delivery, return page, status checks and scheduled tasks." ;;
      check)
        # read-only readiness check before the long wait: is the task registered, are Beat and the worker up, has Beat been sending it
        ok=1
        for svc in celery_worker celery_beat; do
          if [ "$(svc_state "$svc")" = running ]; then echo "OK    $svc is running"; else echo "FAIL  $svc is not running"; ok=0; fi
        done
        if dc exec -T celery_worker celery -A app.core.celery_app inspect registered 2>/dev/null | grep -q 'internship_onboarding.reconcile_payments'; then
          echo "OK    the worker has the task internship_onboarding.reconcile_payments registered"
        else echo "FAIL  the worker does not list the reconciliation task"; ok=0; fi
        if dc logs --no-log-prefix --since 20m celery_beat 2>/dev/null | grep -q 'Sending due task internship-onboarding-reconcile-payments'; then
          echo "OK    Beat has sent the task in the last 20 minutes"
        else echo "WAIT  Beat has not sent it in the last 20 minutes (it fires at :00, :15, :30, :45 UTC; if Beat started recently, check again after the next tick)"; fi
        [ "$ok" = 1 ]
        ;;
      status) recon_status ;;
      report) recon_report "${3:-}" ;;
      run) recon_run "${3:-}" "${4:-45}" ;;
      *) echo "usage: ./staging.sh recon on|off|check|status|report [application ref]|run [application ref] [minutes]"; exit 1 ;;
    esac
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
    gate_warn
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
