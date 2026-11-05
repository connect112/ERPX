#!/usr/bin/env bash
# Cashfree production settings in the ERPX .env file, without ever printing or logging a secret.
#
#   cashfreectl.sh status             what is set (names, and values only for the non-secret ones), and the file's permissions
#   cashfreectl.sh keys               ask for the production App ID and Secret Key (typed hidden, nothing echoed) and store them
#   cashfreectl.sh switches on        the three switches that make live payments possible (asks for a typed confirmation)
#   cashfreectl.sh switches off       turns all three off again (live payments stop being possible); needs no terminal
#
# It edits only CASHFREE_* lines, keeps the file readable by its owner alone (mode 600), and replaces the file in one step so a
# failure cannot leave it half-written. It does not restart anything: recreate api, celery_worker and celery_beat afterwards
# (docs/CASHFREE_PRODUCTION_ACTIVATION.md). Run it as root on the host:  sudo /opt/erpx/ops/cashfree-production/cashfreectl.sh status
#
# Safety rules it enforces: the keys and the live confirmation are only accepted from a real terminal (never piped in, so they cannot end
# up in a script, a pipeline or a shell history); one run at a time (a lock directory next to the file); a symbolic link, a hard-linked
# file, or a folder other users can write to is refused; a temporary copy is removed on any exit, including Ctrl-C and a kill.
# Needs only bash and the standard Linux tools (mktemp, stat, chown, mv): the same on an AWS EC2 host and on any Linux VPS.
set -euo pipefail
ENV_FILE="${ENV_FILE:-/opt/erpx/.env}"
umask 077

TMP_FILE=""        # the temporary copy being written, if any
LOCK_DIR=""        # the lock this run holds, if any

die() { echo "error: $*" >&2; exit 1; }

# Always runs on the way out: removes the temporary copy (it holds every secret in the file), releases the lock, and makes sure the
# terminal echoes again if the run was interrupted while a hidden prompt was open.
cleanup() {
  [ -z "$TMP_FILE" ] || rm -f -- "$TMP_FILE"
  [ -z "$LOCK_DIR" ] || rm -rf -- "$LOCK_DIR"
  if [ -t 0 ]; then stty echo 2>/dev/null || true; fi
}

# Whether keys and confirmations can be typed hidden at a real terminal. Tests replace this function; nothing in production does.
have_terminal() { [ -t 0 ] && [ -t 2 ]; }

need_terminal() {
  have_terminal && return 0
  cat >&2 <<'EOF'
error: this command needs an interactive terminal, so that what you type stays hidden and cannot be piped, scripted or recorded.
Open an SSH session (or a console session that does not record keystrokes) on the host and run it there.
Do not use a remote-command feature, a pipe or a here-document for it. Nothing was changed.
EOF
  exit 2
}

# status only reads, so it may look at a symbolic link; it says so.
check_readable() {
  [ -r "$ENV_FILE" ] || die "$ENV_FILE not found or not readable (run it with sudo?)"
  if [ -L "$ENV_FILE" ]; then echo "note: $ENV_FILE is a symbolic link; changing commands refuse to run on it"; fi
}

# The file must be a plain file we can replace without surprises.
check_target() {
  [ -e "$ENV_FILE" ] || die "$ENV_FILE not found"
  [ ! -L "$ENV_FILE" ] || die "$ENV_FILE is a symbolic link: a replace would swap the link for a plain file and the real file would be left unchanged. Run it on the real file (set ENV_FILE=/path/to/real/.env)"
  [ -f "$ENV_FILE" ] || die "$ENV_FILE is not a regular file"
  local links dir mode
  links="$(stat -c '%h' "$ENV_FILE" 2>/dev/null || echo 1)"
  [ "$links" = "1" ] || die "$ENV_FILE has $links hard links: a replace would break the link and leave the other copy stale"
  dir="$(dirname -- "$ENV_FILE")"
  mode="$(stat -c '%a' "$dir" 2>/dev/null || echo 700)"
  if [ $(( 8#$mode & 8#022 )) -ne 0 ] && [ "$(( 8#$mode & 8#1000 ))" -eq 0 ]; then
    die "$dir can be written to by other users: the temporary copy there could be swapped. Fix the folder's permissions first"
  fi
}

# One run at a time: mkdir is atomic. A lock left by a run that died (its process no longer exists) is cleared once.
acquire_lock() {
  local dir="${ENV_FILE}.cashfreectl.lock" pid attempt
  for attempt in 1 2; do
    if mkdir -- "$dir" 2>/dev/null; then
      LOCK_DIR="$dir"
      echo $$ > "$dir/pid"
      return 0
    fi
    pid="$(cat -- "$dir/pid" 2>/dev/null || true)"
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
      echo "note: clearing a lock left by a run that is no longer running (pid $pid)" >&2
      rm -rf -- "$dir"
      continue
    fi
    die "another cashfreectl run is in progress${pid:+ (pid $pid)}; wait for it, or if it is stuck remove $dir yourself. Nothing was changed"
  done
  die "could not take the lock on $ENV_FILE"
}

# current value of a name ("" when missing); used only for non-secret names and for emptiness checks
get() { grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true; }

# replace (or add) one line, atomically; the value is never printed and never passed to another program as an argument
put() {
  local name="$1" value="$2"
  TMP_FILE="$(mktemp "${ENV_FILE}.XXXXXX")"
  { grep -v -E "^${name}=" "$ENV_FILE" || true; } > "$TMP_FILE"
  printf '%s=%s\n' "$name" "$value" >> "$TMP_FILE"
  chmod 600 "$TMP_FILE"
  chown --reference="$ENV_FILE" "$TMP_FILE" 2>/dev/null || true
  mv -- "$TMP_FILE" "$ENV_FILE"
  TMP_FILE=""
}

tidy_permissions() { chmod 600 "$ENV_FILE"; }

# Cashfree keys are letters, digits, underscore, dash and dot. Anything else (a space, a quote, a $) would be changed by Docker
# Compose's own .env reading, so refuse it rather than store something that silently differs.
check_value() { [[ "$2" =~ ^[A-Za-z0-9_.-]+$ ]] || die "$1 has a character that is not a letter, digit, _ - or . : nothing was changed"; }

main() {
  trap cleanup EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM

  case "${1:-}" in
    status)
      check_readable
      echo "file: $ENV_FILE  mode/owner: $(stat -c '%a %U:%G' "$ENV_FILE" 2>/dev/null || echo unknown)  (want: 600 root:root)"
      for n in CASHFREE_ENABLED CASHFREE_ENV CASHFREE_ALLOW_PRODUCTION CASHFREE_API_VERSION CASHFREE_ORDER_MINUTES CASHFREE_WEBHOOK_MAX_AGE_HOURS; do
        v="$(get "$n")"; echo "$n=${v:-<not set: the default applies>}"
      done
      for n in CASHFREE_APP_ID CASHFREE_SECRET_KEY; do
        if [ -n "$(get "$n")" ]; then echo "$n=<set, hidden>"; else echo "$n=<not set>"; fi
      done
      ;;
    keys)
      need_terminal
      check_target; acquire_lock
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
          need_terminal
          check_target; acquire_lock
          [ -n "$(get CASHFREE_APP_ID)" ] && [ -n "$(get CASHFREE_SECRET_KEY)" ] || die "store the keys first (cashfreectl.sh keys)"
          echo "This lets ERPX take REAL money from students through Cashfree once api, celery_worker and celery_beat are recreated."
          printf 'Type  I AUTHORIZE LIVE PAYMENTS  to continue: '; read -r answer
          [ "$answer" = "I AUTHORIZE LIVE PAYMENTS" ] || die "not confirmed: nothing was changed"
          # ENABLED goes last: if the run is cut short, live payments are still off
          put CASHFREE_ENV production; put CASHFREE_ALLOW_PRODUCTION true; put CASHFREE_API_VERSION 2025-01-01; put CASHFREE_ENABLED true
          tidy_permissions
          echo "Switches set: ENABLED=true ENV=production ALLOW_PRODUCTION=true. Recreate api, celery_worker, celery_beat to apply."
          ;;
        off)
          # needs no terminal: switching off must always be possible, also from a script during an incident
          check_target; acquire_lock
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
}

# Run only when executed, not when a test loads the functions with `source`.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main "$@"; fi
