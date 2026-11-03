#!/usr/bin/env bash
# Regression tests for the staging test gate (./staging.sh gate on|off|status), the isolation used to test the student's
# "I have paid: check status" button on its own:  /bin/bash ops/staging-cashfree/tests/gate_test.sh
# The nginx rules themselves are tested against a real nginx in tests/unit/test_staging_gateway.py; here the script that
# switches them on and off is checked with the fake Docker of fixture.sh (nothing real is touched).
set -uo pipefail

KIT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=fixture.sh
. "$KIT/tests/fixture.sh"
GATEDIR="$REPO/ops/staging-cashfree/gate"

running_stack() { write_env; write_config external; reset_state; own_network 10.253.247.0/24 stale; rm -rf "$GATEDIR"; }
no_network_changes() { forbid_log "network rm"; forbid_log "network create"; }

# 1. gate on: webhook refused + return page blocked + reconciliation stopped, validated before reloading, network untouched
running_stack
run_staging gate on
need_log "up -d --no-deps gateway"
need_log "exec -T gateway nginx -t"
need_log "exec -T gateway nginx -s reload"
need_log "stop celery_beat"
no_network_changes
need_state svc_celery_beat stopped
need_state svc_api running
[ -f "$GATEDIR/block-webhook.conf" ] && [ -f "$GATEDIR/block-return-page.conf" ] || PROBLEMS="$PROBLEMS
      the gate files were not installed"
cmp -s "$GATEDIR/block-webhook.conf" "$KIT/gate-templates/block-webhook.conf" || PROBLEMS="$PROBLEMS
      the installed webhook gate differs from the template"
expect "gate on installs the templates, validates and reloads nginx, stops only the reconciliation" 0 "gate ON" "webhook refused (503)"

# 2. nothing that restarts the reconciliation may run while the gate is on
for cmd in up refresh-app; do
  run_staging "$cmd"
  forbid_log " up -d --build"; forbid_log "force-recreate"
  need_state svc_celery_beat stopped
  expect "$cmd is refused while the gate is on" 1 "the test gate is ON"
done

# 3. status shows the gate and what the gateway saw (so the button can be told apart from a page-load check)
cat > "$FAKE_STATE/gateway_log" <<'LOG'
172.18.0.9 - - [03/Nov/2026:08:01:10 +0000] "POST /api/v1/public/payments/cashfree/webhook HTTP/1.1" 503 190 "-" "Cashfree" "-"
172.18.0.9 - - [03/Nov/2026:08:01:12 +0000] "GET /internship-onboarding?order=ERPXI0123 HTTP/1.1" 200 400 "-" "Mozilla" "-"
172.18.0.9 - - [03/Nov/2026:08:03:40 +0000] "POST /api/v1/public/internship-onboarding/payments/refresh HTTP/1.1" 200 2100 "-" "Mozilla" "-"
LOG
run_staging gate status
expect "gate status reports the gate, the reconciliation and the status checks the gateway saw" 0 \
  "gate: ON" "reconciliation (celery_beat): stopped" "webhook calls (503 = refused):     1" "return-page requests (?order=):    1" \
  "[03/Nov/2026:08:03:40" "/api/v1/public/internship-onboarding/payments/refresh" "made by the student's button"
run_staging status
expect "status warns that the gate is on" 0 "the test gate is ON"

# 4. gate off: files removed, nginx reloaded, reconciliation back, network untouched
run_staging gate off
need_log "start celery_beat"
no_network_changes
need_state svc_celery_beat running
[ ! -e "$GATEDIR/block-webhook.conf" ] && [ ! -e "$GATEDIR/block-return-page.conf" ] || PROBLEMS="$PROBLEMS
      the gate files are still there"
expect "gate off removes the gate and restarts the reconciliation" 0 "gate OFF"
run_staging gate status
expect "gate status after off" 0 "gate: off" "reconciliation (celery_beat): running"
run_staging up
need_log "up -d --build"
expect "up works again after gate off" 0 "ready."

# 5. an invalid gateway configuration is rolled back: the gate files are removed and the reconciliation is not stopped
running_stack; touch "$FAKE_STATE/nginx_invalid"
run_staging gate on
need_state svc_celery_beat running
[ ! -e "$GATEDIR/block-webhook.conf" ] || PROBLEMS="$PROBLEMS
      the rejected gate files were left in place"
expect "a rejected gateway configuration is rolled back" 1 "the gateway refused the gate configuration"

# 6. a wrong argument does nothing
running_stack
run_staging gate sideways
forbid_log "stop celery_beat"
expect "unknown gate argument refused" 1 "usage: ./staging.sh gate on|off|status"

summary
