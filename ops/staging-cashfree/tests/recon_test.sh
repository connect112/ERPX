#!/usr/bin/env bash
# Regression tests for the automatic-reconciliation test mode (./staging.sh recon ...):  /bin/bash ops/staging-cashfree/tests/recon_test.sh
# recon keeps Celery Beat and the worker RUNNING while the webhook, the return-page check and every student status check
# are kept out; its report decides from the gateway, Beat and worker logs and the database whether the scheduled task did
# the confirmation. The nginx rules are tested against a real nginx (tests/unit/test_staging_gateway.py), the SQL against a
# real PostgreSQL (tests/api/test_internship_onboarding_reconcile_task.py); here the script is checked with the fake Docker.
set -uo pipefail

KIT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=fixture.sh
. "$KIT/tests/fixture.sh"
GATEDIR="$REPO/ops/staging-cashfree/gate"
APP=ERPX-INT-2026-000009

running_stack() { write_env; write_config external; reset_state; own_network 10.253.247.0/24 stale; rm -rf "$GATEDIR" "$REPO/ops/staging-cashfree/evidence"; }
no_network_changes() { forbid_log "network rm"; forbid_log "network create"; }

# --- canned evidence of a successful run, as the real logs and recon.sql would show it
pass_logs() {
  cat > "$FAKE_STATE/gateway_log" <<'LOG'
172.18.0.9 - - [03/Nov/2026:08:01:10 +0000] "POST /api/v1/public/payments/cashfree/webhook HTTP/1.1" 503 190 "-" "Cashfree" "-"
172.18.0.9 - - [03/Nov/2026:08:03:10 +0000] "POST /api/v1/public/payments/cashfree/webhook HTTP/1.1" 503 190 "-" "Cashfree" "-"
172.18.0.9 - - [03/Nov/2026:08:01:12 +0000] "GET /internship-onboarding?order=ERPXI0123 HTTP/1.1" 200 400 "-" "Mozilla" "-"
LOG
  cat > "$FAKE_STATE/beat_log" <<'LOG'
2026-11-03T08:30:00.000100000Z [2026-11-03 08:30:00,001: INFO/MainProcess] Scheduler: Sending due task internship-onboarding-reconcile-payments (internship_onboarding.reconcile_payments)
LOG
  cat > "$FAKE_STATE/worker_log" <<'LOG'
2026-11-03T08:30:00.020000000Z [2026-11-03 08:30:00,020: INFO/MainProcess] Task internship_onboarding.reconcile_payments[abc-123] received
2026-11-03T08:30:01.000000000Z HTTP Request: GET https://sandbox.cashfree.com/pg/orders/ERPXI0123/payments "HTTP/1.1 200 OK"
2026-11-03T08:30:01.800000000Z [2026-11-03 08:30:01,800: INFO/ForkPoolWorker-1] Task internship_onboarding.reconcile_payments[abc-123] succeeded in 1.7s: {'checked': 1, 'confirmed': 1}
LOG
  echo '{"messages":[{"ID":"m1","Subject":"Receipt RCPT-2026-000007"}]}' > "$FAKE_STATE/mail_json"
}
pass_facts() {
  cat > "$FAKE_STATE/recon_facts" <<'FACTS'
fact.application=ERPX-INT-2026-000009
fact.order=ERPXI0123
fact.order_status=paid
fact.order_created_at=2026-11-03T08:12:00Z
fact.order_last_checked_at=2026-11-03T08:30:01Z
fact.order_paid_at=2026-11-03T08:30:01Z
fact.cashfree_payment_id=1471099999999999999
fact.confirmed_payments=1
fact.receipts=1
fact.receipt_number=RCPT-2026-000007
fact.confirmed_events=1
fact.confirmed_event_at=2026-11-03T08:30:01Z
fact.confirmed_event_source=status check
fact.notifications_that_reached_erpx=0
check.paid_by_one_payment_one_receipt_one_event=true
check.test_mode_was_on_before_checkout=true
check.confirmed_at_least_10_minutes_after_checkout=true
check.confirmation_source_is_status_check=true
check.order_last_checked_at_matches_confirmation=true
check.confirmation_inside_scheduled_task_run=true
check.no_notification_reached_erpx=true
integrity.payments_recorded_twice=0
integrity.documents_issued_twice=0
integrity.confirmed_without_document=0
integrity.refund_adjustment_mismatches=0
integrity.accounting_journal_entries=0
FACTS
}
started() { running_stack; run_staging recon on; }

# 1. recon on: isolation installed, Beat and the worker NOT touched, validated, network untouched
running_stack
run_staging recon on
need_log "up -d --no-deps gateway"; need_log "exec -T gateway nginx -t"; need_log "exec -T gateway nginx -s reload"
forbid_log " stop"; forbid_log "restart"; no_network_changes
need_state svc_celery_beat running; need_state svc_celery_worker running; need_state svc_api running
for f in block-webhook.conf block-return-page.conf block-status-refresh.conf; do
  cmp -s "$GATEDIR/$f" "$KIT/gate-templates/$f" 2>/dev/null || cmp -s "$GATEDIR/$f" "$KIT/gate-templates/reconcile/$f" || PROBLEMS="$PROBLEMS
      $f is not installed from its template"
done
[ "$(cat "$GATEDIR/mode")" = reconcile ] || PROBLEMS="$PROBLEMS
      the mode file does not say reconcile"
expect "recon on refuses webhook, return page and status checks, leaves Beat and the worker running" 0 "recon mode ON" "RUNNING and untouched"

# 2. the two modes exclude each other, and nothing may restart the containers the test relies on
for cmd in "gate on" "recon on" up refresh-app; do
  # shellcheck disable=SC2086
  run_staging $cmd
  forbid_log "stop celery_beat"; forbid_log " up -d --build"; forbid_log "force-recreate"
  expect "'$cmd' is refused while recon is on" 1 "a staging test mode"
done
need_state svc_celery_beat running

# 3. status: counters from the gateway, the Beat and worker lines
pass_logs
run_staging recon status
expect "recon status shows the mode, the gateway counters and the scheduled runs" 0 "mode: ON (reconcile)" "celery_beat: running" \
  "refused with 503: 2" "payment return-page requests blocked: 1" "student status-check calls: 0" \
  "beat sent the task at 2026-11-03T08:30:00" "worker ran it at 2026-11-03T08:30:01"

# 4. check: readiness before the long wait. The log lines below follow the formats of Celery 5.4 and `docker compose logs --timestamps`
#    (Beat "Scheduler: Sending due task <entry> (<task>)", worker "Task <name>[<id>] received/succeeded in ...: {...}", the
#    worker's "[tasks]" list at start, and the reply of `celery inspect registered`).
beat_line() {  # <minutes ago> <entry> <task>
  ts="$(iso_ago "$1")"
  echo "${ts}.004123456Z [$(echo "$ts" | tr T ' '),003: INFO/MainProcess] Scheduler: Sending due task $2 ($3)"
}
healthy_logs() {
  { beat_line 20 internship-onboarding-sweep internship_onboarding.sweep; beat_line 5 internship-onboarding-reconcile-payments internship_onboarding.reconcile_payments
    beat_line 2 internship-onboarding-sweep internship_onboarding.sweep; } > "$FAKE_STATE/beat_log"
  ts="$(iso_ago 5)"
  cat > "$FAKE_STATE/worker_log" <<LOG
 -------------- celery@8f3a2b1c9d0e v5.4.0 (opalescent)
[tasks]
  . internship_onboarding.reconcile_payments
  . internship_onboarding.sweep
${ts}.020000000Z [$(echo "$ts" | tr T ' '),019: INFO/MainProcess] Task internship_onboarding.reconcile_payments[9f1c2d3e-0a1b-4c5d-8e9f-001122334455] received
${ts}.080000000Z [$(echo "$ts" | tr T ' '),079: INFO/ForkPoolWorker-1] Task internship_onboarding.reconcile_payments[9f1c2d3e-0a1b-4c5d-8e9f-001122334455] succeeded in 0.05s: {'checked': 0, 'confirmed': 0}
LOG
}
running_stack; healthy_logs
run_staging recon check
forbid_log " stop"; forbid_log " start"; forbid_log "restart"; forbid_log " up "; no_network_changes   # read-only
need_log "inspect registered -t 20 -d"
expect "recon check: healthy (inspect answers, Beat ticked 5 minutes ago, the worker ran it)" 0 \
  "OK    celery_beat is running" "registered (celery inspect)" "OK    Beat last sent the task at $(iso_ago 5)" \
  "INFO  the worker last ran it at $(iso_ago 5)Z: {'checked': 0, 'confirmed': 0}"

# a reply larger than the pipe buffer that arrives in two chunks: a pipeline ending in `grep -q` reports "not found" for it under pipefail (the real reply is small, about 1.5 KB; this pins the hazard class down)
running_stack; healthy_logs
{ echo "->  celery@8f3a2b1c9d0e: OK"; echo "    * celery.accumulate"; echo "    * celery.backend_cleanup"; echo "    * internship_onboarding.reconcile_payments"
  for i in $(seq 1 40000); do echo "    * module.task_$i"; done; } > "$FAKE_STATE/registered_slow"
run_staging recon check
expect "recon check: a long inspect reply that arrives in chunks is still found" 0 "registered (celery inspect)"

# inspect timing out is not a missing task: the worker's own log is evidence, and the inspect answer is shown
running_stack; healthy_logs; echo "Error: No nodes replied within time constraint" > "$FAKE_STATE/registered_error"
run_staging recon check
expect "recon check: inspect times out but the worker log lists and ran the task" 0 \
  "OK    the worker's own log lists or ran the task" "No nodes replied within time constraint" "OK    Beat last sent the task"
# ...and when nothing shows the task, it fails and says why
running_stack; healthy_logs; echo "Error: No nodes replied within time constraint" > "$FAKE_STATE/registered_error"; : > "$FAKE_STATE/worker_log"
run_staging recon check
expect "recon check: no sign of the task anywhere is a FAIL that shows what inspect said" 1 \
  "FAIL  neither celery inspect nor the worker's log shows the task" "No nodes replied within time constraint" "INFO  the worker has not run it yet"
# a mere mention in an error is not registration
running_stack; healthy_logs; echo "Error: No nodes replied within time constraint" > "$FAKE_STATE/registered_error"
echo "[ERROR/MainProcess] Received unregistered task of type 'internship_onboarding.reconcile_payments'" > "$FAKE_STATE/worker_log"
run_staging recon check
expect "recon check: an 'unregistered task' error does not count as registered" 1 "FAIL  neither celery inspect nor the worker's log shows the task"

# Beat: the newest matching tick is judged by its timestamp, other tasks do not count, no tick yet waits, a stale one is shown
running_stack; healthy_logs; beat_line 40 internship-onboarding-reconcile-payments internship_onboarding.reconcile_payments > "$FAKE_STATE/beat_log"
run_staging recon check
expect "recon check: a tick older than 20 minutes is reported with its time, not hidden" 0 "WAIT  Beat last sent the task at $(iso_ago 40)Z, more than 20 minutes ago"
running_stack; healthy_logs; { beat_line 3 internship-onboarding-sweep internship_onboarding.sweep; beat_line 17 other-task other.task; } > "$FAKE_STATE/beat_log"
run_staging recon check
expect "recon check: ticks of other tasks do not count" 0 "WAIT  Beat's log has no 'Sending due task ... reconcile' line yet"
running_stack; healthy_logs; echo "[$(iso_ago 4 | tr T ' '),003: INFO/MainProcess] Scheduler: Sending due task internship-onboarding-reconcile-payments (internship_onboarding.reconcile_payments)" > "$FAKE_STATE/beat_log"
run_staging recon check
expect "recon check: Celery's own timestamp is used when Docker's is missing" 0 "OK    Beat last sent the task at $(iso_ago 4)Z"
running_stack; healthy_logs; echo stopped > "$FAKE_STATE/svc_celery_beat"
run_staging recon check
expect "recon check: Beat stopped is a FAIL" 1 "FAIL  celery_beat is not running"
running_stack; healthy_logs; echo stopped > "$FAKE_STATE/svc_celery_worker"
run_staging recon check
expect "recon check: the worker stopped is a FAIL" 1 "FAIL  celery_worker is not running"

# 5. report: every criterion met
started; pass_logs; pass_facts
run_staging recon report "$APP"
latest="$(ls -d "$REPO"/ops/staging-cashfree/evidence/recon-* 2>/dev/null | tail -1)"
[ -f "$latest/report.txt" ] && [ -f "$latest/facts.txt" ] || PROBLEMS="$PROBLEMS
      the report files were not saved"
grep -q "sandbox.cashfree.com" "$latest/worker-lines.txt" 2>/dev/null || PROBLEMS="$PROBLEMS
      the Cashfree API request line was not kept in the worker lines"
grep -q 'cfsk_\|secret\|x-webhook-signature' "$latest"/* 2>/dev/null && PROBLEMS="$PROBLEMS
      the saved files contain something that looks like a secret"
expect "report: every criterion met" 0 "PASS  Celery Beat sent the reconciliation task (1 time(s)" "PASS  the worker ran it and it confirmed at least one payment" \
  "PASS  ERPX recorded the confirmation inside that run" "PASS  exactly one receipt email in Mailpit for RCPT-2026-000007 (found 1)" "RESULT: every criterion is met"

# 6. report: each way the test can be invalid or fail is named, and nothing is claimed
report_fails() {  # <name> <text that must be reported as not met>
  run_staging recon report "$APP"
  expect "report: $1" 1 "RESULT: NOT PROVEN" "FAIL  $2"
}
pass_logs; pass_facts
echo '172.18.0.9 - - [03/Nov/2026:08:29:00 +0000] "POST /api/v1/public/internship-onboarding/payments/refresh HTTP/1.1" 200 2100 "-" "Mozilla" "-"' >> "$FAKE_STATE/gateway_log"
report_fails "a student status check that reached ERPX invalidates the test" "no student status check reached ERPX (1 reached"
pass_logs; pass_facts
echo '172.18.0.9 - - [03/Nov/2026:08:05:00 +0000] "POST /api/v1/public/payments/cashfree/webhook HTTP/1.1" 200 90 "-" "Cashfree" "-"' >> "$FAKE_STATE/gateway_log"
report_fails "a webhook the gateway accepted invalidates the test" "no Cashfree notification was accepted by the gateway (1 non-503"
pass_logs; pass_facts; grep -v "succeeded" "$FAKE_STATE/worker_log" > "$FAKE_STATE/w" && mv "$FAKE_STATE/w" "$FAKE_STATE/worker_log"
sed -i.bak 's/^check.confirmation_inside_scheduled_task_run=true/check.confirmation_inside_scheduled_task_run=false/' "$FAKE_STATE/recon_facts"
report_fails "no scheduled run that confirmed anything" "the worker ran it and it confirmed at least one payment"
pass_logs; pass_facts; : > "$FAKE_STATE/beat_log"
report_fails "Beat never sent the task" "Celery Beat sent the reconciliation task (0 time(s)"
pass_logs; pass_facts
sed -i.bak 's/^check.confirmed_at_least_10_minutes_after_checkout=true/check.confirmed_at_least_10_minutes_after_checkout=false/' "$FAKE_STATE/recon_facts"
report_fails "confirmed sooner than the task's minimum order age" "confirmation came at least 10 minutes after checkout"
pass_logs; pass_facts
sed -i.bak 's/^confirmed_event_source=status check/x=y/; s/^fact.confirmed_event_source=status check/fact.confirmed_event_source=webhook/; s/^check.confirmation_source_is_status_check=true/check.confirmation_source_is_status_check=false/' "$FAKE_STATE/recon_facts"
report_fails "confirmed by something other than a status check" "the confirmation's source is 'status check'"
pass_logs; pass_facts; echo '{"messages":[{"ID":"m1","Subject":"Receipt RCPT-2026-000007"},{"ID":"m2","Subject":"Receipt RCPT-2026-000007"}]}' > "$FAKE_STATE/mail_json"
report_fails "two receipt emails" "exactly one receipt email in Mailpit for RCPT-2026-000007 (found 2)"
pass_logs; pass_facts; sed -i.bak 's/^integrity.documents_issued_twice=0/integrity.documents_issued_twice=1/' "$FAKE_STATE/recon_facts"
report_fails "an integrity check not 0" "the five integrity checks are all 0"
pass_logs; pass_facts; sed -i.bak 's/^check.paid_by_one_payment_one_receipt_one_event=true/check.paid_by_one_payment_one_receipt_one_event=false/' "$FAKE_STATE/recon_facts"
report_fails "not exactly one payment, receipt and event" "paid, with exactly one confirmed payment, one receipt and one payment_confirmed event"
run_staging recon report 'ERPX;drop'
expect "report refuses an application reference with odd characters" 2 "only letters, digits and dashes"

# 7. recon off: the way back, every time
started; echo stopped > "$FAKE_STATE/svc_celery_beat"; echo stopped > "$FAKE_STATE/svc_celery_worker"
run_staging recon off
need_log "start celery_beat celery_worker"; no_network_changes
need_state svc_celery_beat running; need_state svc_celery_worker running
[ ! -e "$GATEDIR/block-webhook.conf" ] && [ ! -e "$GATEDIR/block-return-page.conf" ] && [ ! -e "$GATEDIR/block-status-refresh.conf" ] && [ ! -e "$GATEDIR/mode" ] || PROBLEMS="$PROBLEMS
      gate files or the mode file are still there"
expect "recon off removes the gate, reloads nginx and brings Beat and the worker back" 0 "restored: webhook, return page and status checks reach ERPX again" "recon OFF"
run_staging recon off
expect "recon off is safe to run again" 0 "recon OFF"
started; touch "$FAKE_STATE/nginx_invalid"
run_staging recon off
need_file restarts
[ ! -e "$GATEDIR/block-webhook.conf" ] || PROBLEMS="$PROBLEMS
      the gate files were left in place"
expect "recon off still restores everything when nginx cannot be reloaded (restarts only the gateway)" 0 "restarting the gateway only" "restored:"
need_log "restart gateway"; forbid_log "restart api"; forbid_log "restart postgres"

# 8. a failed start rolls itself back
running_stack; touch "$FAKE_STATE/nginx_invalid"
run_staging recon on
[ ! -e "$GATEDIR/block-webhook.conf" ] || PROBLEMS="$PROBLEMS
      the rejected gate files were left in place"
need_state svc_celery_beat running
expect "recon on rolls back when nginx rejects the configuration" 1 "the gateway refused the gate configuration"
running_stack; echo stopped > "$FAKE_STATE/svc_celery_beat"
FAKE_START_FAILS=1 run_staging recon on
[ ! -e "$GATEDIR/block-webhook.conf" ] || PROBLEMS="$PROBLEMS
      gate files were installed although Beat is not running"
expect "recon on refuses to start when Beat cannot be running" 1 "celery_beat is not running"

# 9. recon run: enables, waits, reports, and ALWAYS rolls back
running_stack; pass_logs; pass_facts; echo 1 > "$FAKE_STATE/paid_count"
run_staging recon run "$APP" 1
need_log "exec -T gateway nginx -s reload"; need_log "start celery_beat celery_worker"
[ ! -e "$GATEDIR/block-webhook.conf" ] && [ ! -e "$GATEDIR/mode" ] || PROBLEMS="$PROBLEMS
      the gate was not rolled back after the run"
expect "recon run: payment seen, report passed, rolled back" 0 "paid in ERPX." "RESULT: every criterion is met" "== rollback" "restored:"
running_stack; pass_logs; rm -f "$FAKE_STATE/recon_facts"; echo 0 > "$FAKE_STATE/paid_count"   # nothing paid: the database shows no paid order
run_staging recon run "$APP" 1
[ ! -e "$GATEDIR/block-webhook.conf" ] || PROBLEMS="$PROBLEMS
      the gate was not rolled back after a timeout"
expect "recon run: nothing paid in time, report not proven, still rolled back" 1 "not paid in ERPX within 1 minutes" "== rollback" "restored:"
running_stack; pass_logs; pass_facts; echo 1 > "$FAKE_STATE/paid_count"; sed -i.bak 's/^check.no_notification_reached_erpx=true/check.no_notification_reached_erpx=false/' "$FAKE_STATE/recon_facts"
run_staging recon run "$APP" 1
[ ! -e "$GATEDIR/block-webhook.conf" ] || PROBLEMS="$PROBLEMS
      the gate was not rolled back after a failed report"
expect "recon run: failed report, still rolled back" 1 "RESULT: NOT PROVEN" "== rollback"
# a mode that is already on is not touched by a second run
started
run_staging recon run "$APP" 1
[ -f "$GATEDIR/block-webhook.conf" ] || PROBLEMS="$PROBLEMS
      a refused second run removed the gate of the run in progress"
expect "recon run refuses while a mode is on and leaves it alone" 1 "already on"
run_staging recon off

# 10. a signal or a closed terminal during the wait also rolls back
running_stack; pass_logs; pass_facts; echo 0 > "$FAKE_STATE/paid_count"
env "${CLEAR[@]}" PATH="$WORK/bin:$PATH" FAKE_SLEEP=1 "$SHELL_UNDER_TEST" "$REPO/ops/staging-cashfree/staging.sh" recon run "$APP" 5 > "$WORK/out.txt" 2>&1 &
pid=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -f "$GATEDIR/mode" ] && break; /bin/sleep 0.5; done
[ -f "$GATEDIR/mode" ] || PROBLEMS="$PROBLEMS
      the run never installed the gate"
kill -TERM "$pid" 2>/dev/null
wait "$pid" 2>/dev/null; echo $? > "$WORK/status.txt"
[ ! -e "$GATEDIR/block-webhook.conf" ] && [ ! -e "$GATEDIR/mode" ] || PROBLEMS="$PROBLEMS
      the gate was still in place after SIGTERM"
need_log "start celery_beat celery_worker"
expect "recon run: SIGTERM during the wait rolls everything back" 143 "== rollback" "restored:"

summary
