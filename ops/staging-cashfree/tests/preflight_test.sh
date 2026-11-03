#!/usr/bin/env bash
# Regression tests for preflight.sh, run under the bash that runs this file:
#   /bin/bash ops/staging-cashfree/tests/preflight_test.sh      (on macOS this is bash 3.2)
# Each case runs the real preflight.sh in a throwaway git repository with a fake `docker` (no Docker, no network, no
# real staging.env touched) and checks its verdict. Exit status 0 = all cases passed.
set -uo pipefail

KIT="$(cd "$(dirname "$0")/.." && pwd)"
SHELL_UNDER_TEST="${BASH:-bash}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/preflight-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
PASSED=0
FAILED=0

echo "bash under test: $SHELL_UNDER_TEST ($("$SHELL_UNDER_TEST" -c 'echo $BASH_VERSION'))"

# --- a throwaway repository holding the kit, like the real checkout
REPO="$WORK/repo"
mkdir -p "$REPO/ops/staging-cashfree" "$WORK/bin"
cp "$KIT/preflight.sh" "$KIT/staging.sh" "$KIT/staging.env.example" "$KIT/compose.yml" "$KIT/.gitignore" "$REPO/ops/staging-cashfree/"
(cd "$REPO" && git init -q && git add -A && git -c user.name=test -c user.email=test@example.com commit -qm fixture)
ENVF="$REPO/ops/staging-cashfree/staging.env"

# --- a fake docker: answers exactly what preflight asks, from FAKE_* variables
cat > "$WORK/bin/docker" <<'FAKE'
#!/bin/sh
subnet_of() {
  case "$1" in
    own) echo "${FAKE_OWN_SUBNET:-}" ;;
    other) echo "${FAKE_OTHER_SUBNET:-}" ;;
    bridge) echo "172.17.0.0/16" ;;
  esac
}
case "$1" in
  info)
    [ "${2:-}" = "--format" ] && echo 8000000000
    exit 0 ;;
  ps) exit 0 ;;
  compose)
    [ "${2:-}" = "version" ] && { echo 2.30.0; exit 0; }
    cat "$FAKE_CONFIG"; exit 0 ;;
  network)
    if [ "$2" = "ls" ]; then
      case "$*" in
        *label=*) [ -n "${FAKE_OWN_SUBNET:-}" ] && echo own ;;
        *) [ -n "${FAKE_OWN_SUBNET:-}" ] && echo own; [ -n "${FAKE_OTHER_SUBNET:-}" ] && echo other; echo bridge ;;
      esac
      exit 0
    fi
    if [ "$2" = "inspect" ]; then
      case "$*" in
        *.Name*) echo "$3" ;;
        *) subnet_of "$3" ;;
      esac
      exit 0
    fi ;;
esac
exit 0
FAKE
chmod +x "$WORK/bin/docker"

# what `docker compose config` renders for this kit (the parts preflight checks)
FAKE_CONFIG="$WORK/config.yml"
{
  echo "name: erpx-cf-staging"
  echo "services:"
  for svc in api celery_worker celery_beat; do
    printf '  %s:\n    environment:\n      CASHFREE_ENV: sandbox\n      CASHFREE_ALLOW_PRODUCTION: "false"\n      ENVIRONMENT: staging\n' "$svc"
  done
  for port in 18080 18025; do
    printf '  svc%s:\n    ports:\n      - mode: ingress\n        host_ip: 127.0.0.1\n        target: 80\n        published: "%s"\n' "$port" "$port"
  done
} > "$FAKE_CONFIG"
export FAKE_CONFIG

# a complete, valid staging.env (dummy values; never real keys)
write_env() {
  cat > "$ENVF" <<ENV
# staging settings (test fixture)
CASHFREE_APP_ID=TESTdummynotarealappid
CASHFREE_SECRET_KEY=cfsk_ma_test_dummy_not_a_real_key
CASHFREE_API_VERSION=2025-01-01
STAGING_PUBLIC_URL=https://quiet-river-1234.trycloudflare.com
STAGING_HTTP_PORT=18080
STAGING_MAIL_PORT=18025
STAGING_SUBNET=10.253.247.0/24
POSTGRES_PASSWORD=pg$(date +%s)a1b2c3d4e5f6a7b8c9d0
MINIO_ROOT_USER=erpx-staging
MINIO_ROOT_PASSWORD=mn$(date +%s)a1b2c3d4e5f6a7b8c9d0
JWT_SECRET_KEY=jw$(date +%s)a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6
SEED_SUPERADMIN_EMAIL=staging-superadmin@example.com
SEED_SUPERADMIN_PASSWORD=Sa-$(date +%s)a1b2c3d4e5f6
STAGING_ADMIN_EMAIL=staging-admin@example.com
STAGING_ADMIN_PASSWORD=Ad-$(date +%s)a1b2c3d4e5f6
ENV
}

# every setting preflight would treat as a shell override (all documented ones, plus the fixed Cashfree switches)
CLEAR=()
for k in $(awk '{ sub(/\r$/, "") } match($0, /^#?[ ]*[A-Z_][A-Z0-9_]*=/) { k = substr($0, RSTART, RLENGTH - 1); sub(/^#?[ ]*/, "", k); print k }' \
             "$KIT/staging.env.example") CASHFREE_ENV CASHFREE_ENABLED CASHFREE_ALLOW_PRODUCTION DATABASE_URL; do
  CLEAR+=(-u "$k")
done

run_preflight() {
  env "${CLEAR[@]}" PATH="$WORK/bin:$PATH" "$SHELL_UNDER_TEST" "$REPO/ops/staging-cashfree/preflight.sh" > "$WORK/out.txt" 2>&1
  echo $? > "$WORK/status.txt"
}

# expect <name> <exit status> <text that must appear>... ; also never a shell error
expect() {
  local name="$1" want_status="$2" got_status ok=1 text
  shift 2
  got_status="$(cat "$WORK/status.txt")"
  [ "$got_status" = "$want_status" ] || ok=0
  for text in "$@"; do grep -qF -- "$text" "$WORK/out.txt" || ok=0; done
  if grep -qE "syntax error|unbound variable|command not found|bad substitution" "$WORK/out.txt"; then ok=0; fi
  if [ "$ok" = 1 ]; then echo "PASS  $name"; PASSED=$((PASSED + 1))
  else
    echo "FAIL  $name (exit $got_status, wanted $want_status)"; sed 's/^/      /' "$WORK/out.txt"; FAILED=$((FAILED + 1))
  fi
}

# 1. the scripts parse under this bash
if "$SHELL_UNDER_TEST" -n "$KIT/preflight.sh" && "$SHELL_UNDER_TEST" -n "$KIT/staging.sh"; then
  echo "PASS  scripts parse"; PASSED=$((PASSED + 1))
else echo "FAIL  scripts parse"; FAILED=$((FAILED + 1)); fi

# 2. every documented setting is allowed, with the Mac's existing subnet already in use by this stack (no recreation)
write_env
FAKE_OWN_SUBNET=10.253.247.0/24 FAKE_OTHER_SUBNET=10.213.47.0/24 run_preflight
expect "allowed settings + existing STAGING_SUBNET 10.253.247.0/24 (no network recreation)" 0 \
  "only staging settings in staging.env" "dedicated subnet 10.253.247.0/24 overlaps no other" "preflight: all checks passed"

# 3. optional settings documented as comments in staging.env.example are allowed too
write_env; printf 'STAGING_MINIO_IMAGE=pgsty/minio:RELEASE.2026-08-04T00-00-00Z\nSTAGING_CASHFREE_KEY_CHECK=relaxed\n' >> "$ENVF"
FAKE_OWN_SUBNET=10.253.247.0/24 run_preflight
expect "optional documented settings" 0 "only staging settings in staging.env"

# 4. unexpected variables are refused, each named
write_env; printf 'DATABASE_URL=postgresql://x@y/z\nSTAGING_FOO=bar\n' >> "$ENVF"
FAKE_OWN_SUBNET=10.253.247.0/24 run_preflight
expect "unexpected variables refused" 1 "unexpected settings in staging.env" "DATABASE_URL" "STAGING_FOO"

# 5. CRLF line endings: keys still recognised, values read, a warning shown
write_env; awk '{ printf "%s\r\n", $0 }' "$ENVF" > "$ENVF.crlf" && mv "$ENVF.crlf" "$ENVF"
FAKE_OWN_SUBNET=10.253.247.0/24 run_preflight
expect "CRLF line endings" 0 "Windows line endings" "only staging settings in staging.env" "dedicated subnet 10.253.247.0/24"

# 6. a last line without a newline is still checked
write_env; printf 'STAGING_FOO=bar' >> "$ENVF"
FAKE_OWN_SUBNET=10.253.247.0/24 run_preflight
expect "last line without newline" 1 "STAGING_FOO"

# 7. this stack's network on a different subnet than STAGING_SUBNET is still refused (validation kept)
write_env
FAKE_OWN_SUBNET=172.30.9.0/24 run_preflight
expect "existing network on another subnet refused" 1 "uses 172.30.9.0/24, not 10.253.247.0/24"

# 8. overlap with another Docker network is still refused
write_env
FAKE_OWN_SUBNET="" FAKE_OTHER_SUBNET=10.253.0.0/16 run_preflight
expect "overlap with another network refused" 1 "overlaps: other(10.253.0.0/16)"

# 9. a malformed STAGING_SUBNET is refused
write_env; awk '{ sub(/^STAGING_SUBNET=.*/, "STAGING_SUBNET=10.253.247.0/8"); print }' "$ENVF" > "$ENVF.tmp" && mv "$ENVF.tmp" "$ENVF"
FAKE_OWN_SUBNET="" run_preflight
expect "malformed subnet refused" 1 "must be an IPv4 network from /16 to /28"

# 10. a shell variable that would override staging.env is still refused
write_env
env "${CLEAR[@]}" JWT_SECRET_KEY=from-the-shell PATH="$WORK/bin:$PATH" FAKE_OWN_SUBNET=10.253.247.0/24 \
  "$SHELL_UNDER_TEST" "$REPO/ops/staging-cashfree/preflight.sh" > "$WORK/out.txt" 2>&1
echo $? > "$WORK/status.txt"
expect "shell override refused" 1 "these shell variables would override staging.env" "JWT_SECRET_KEY"

echo "$PASSED passed, $FAILED failed"
[ "$FAILED" -eq 0 ]
