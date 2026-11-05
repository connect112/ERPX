#!/usr/bin/env bash
# Cashfree production settings in /opt/erpx/.env, without ever printing or logging a secret.
#
#   cashfreectl.sh status             what is set (names, and values only for the non-secret ones), and the file's permissions
#   cashfreectl.sh keys               ask for the production App ID and Secret Key (typed hidden, nothing echoed) and store them
#   cashfreectl.sh switches on        the three switches that make live payments possible (asks for a typed confirmation)
#   cashfreectl.sh switches off       turns all three off again (live payments stop being possible)
#
# It edits only CASHFREE_* lines, keeps the file readable by its owner alone (mode 600), and replaces the file in one step so a
# failure cannot leave it half-written. It does not restart anything: recreate api, celery_worker and celery_beat afterwards
# (docs/CASHFREE_PRODUCTION_ACTIVATION.md). Run it as root on the host:  sudo /opt/erpx/ops/cashfree-production/cashfreectl.sh status
set -euo pipefail
ENV_FILE="${ENV_FILE:-/opt/erpx/.env}"
umask 077

die() { echo "error: $*" >&2; exit 1; }
[ -f "$ENV_FILE" ] || die "$ENV_FILE not found"

# current value of a name ("" when missing); used only for non-secret names and for emptiness checks
get() { grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true; }

# replace (or add) one line, atomically; the value is never printed
put() {
  local name="$1" value="$2" tmp
  tmp="$(mktemp "${ENV_FILE}.XXXXXX")"
  { grep -v -E "^${name}=" "$ENV_FILE" || true; } > "$tmp"
  printf '%s=%s\n' "$name" "$value" >> "$tmp"
  chmod 600 "$tmp"
  chown --reference="$ENV_FILE" "$tmp" 2>/dev/null || true
  mv "$tmp" "$ENV_FILE"
}

tidy_permissions() { chmod 600 "$ENV_FILE"; }

# Cashfree keys are letters, digits, underscore, dash and dot. Anything else (a space, a quote, a $) would be changed by Docker
# Compose's own .env reading, so refuse it rather than store something that silently differs.
check_value() { [[ "$2" =~ ^[A-Za-z0-9_.-]+$ ]] || die "$1 has a character that is not a letter, digit, _ - or . : nothing was changed"; }

case "${1:-}" in
  status)
    echo "file: $ENV_FILE  mode/owner: $(stat -c '%a %U:%G' "$ENV_FILE" 2>/dev/null || echo unknown)  (want: 600 root:root)"
    for n in CASHFREE_ENABLED CASHFREE_ENV CASHFREE_ALLOW_PRODUCTION CASHFREE_API_VERSION CASHFREE_ORDER_MINUTES CASHFREE_WEBHOOK_MAX_AGE_HOURS; do
      v="$(get "$n")"; echo "$n=${v:-<not set: the default applies>}"
    done
    for n in CASHFREE_APP_ID CASHFREE_SECRET_KEY; do
      if [ -n "$(get "$n")" ]; then echo "$n=<set, hidden>"; else echo "$n=<not set>"; fi
    done
    ;;
  keys)
    printf 'Production App ID (typing is hidden): '; read -r -s app_id; echo
    printf 'Production Secret Key (typing is hidden): '; read -r -s secret; echo
    printf 'Secret Key again: '; read -r -s again; echo
    [ -n "$app_id" ] && [ -n "$secret" ] || die "both values are needed: nothing was changed"
    [ "$secret" = "$again" ] || die "the two Secret Keys differ: nothing was changed"
    check_value CASHFREE_APP_ID "$app_id"; check_value CASHFREE_SECRET_KEY "$secret"
    put CASHFREE_APP_ID "$app_id"; put CASHFREE_SECRET_KEY "$secret"
    unset app_id secret again
    tidy_permissions
    echo "Stored CASHFREE_APP_ID and CASHFREE_SECRET_KEY (values not shown). Switches were not changed."
    ;;
  switches)
    case "${2:-}" in
      on)
        [ -n "$(get CASHFREE_APP_ID)" ] && [ -n "$(get CASHFREE_SECRET_KEY)" ] || die "store the keys first (cashfreectl.sh keys)"
        echo "This lets ERPX take REAL money from students through Cashfree once api, celery_worker and celery_beat are recreated."
        printf 'Type  I AUTHORIZE LIVE PAYMENTS  to continue: '; read -r answer
        [ "$answer" = "I AUTHORIZE LIVE PAYMENTS" ] || die "not confirmed: nothing was changed"
        put CASHFREE_ENV production; put CASHFREE_ALLOW_PRODUCTION true; put CASHFREE_API_VERSION 2025-01-01; put CASHFREE_ENABLED true
        tidy_permissions
        echo "Switches set: ENABLED=true ENV=production ALLOW_PRODUCTION=true. Recreate api, celery_worker, celery_beat to apply."
        ;;
      off)
        put CASHFREE_ENABLED false; put CASHFREE_ALLOW_PRODUCTION false; put CASHFREE_ENV sandbox
        tidy_permissions
        echo "Switches set: ENABLED=false ALLOW_PRODUCTION=false ENV=sandbox. Recreate api, celery_worker, celery_beat to apply."
        echo "Reminder: while ENABLED=false the webhook answers 503 and nothing is reconciled (see the rollback section of the guide)."
        ;;
      *) die "usage: cashfreectl.sh switches on|off" ;;
    esac
    ;;
  *) die "usage: cashfreectl.sh status | keys | switches on|off" ;;
esac
