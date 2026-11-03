#!/usr/bin/env bash
# Regression tests for preflight.sh, run under the bash that runs this file:
#   /bin/bash ops/staging-cashfree/tests/preflight_test.sh      (on macOS this is bash 3.2)
# Each case runs the real preflight.sh in a throwaway git repository with a fake `docker` (see fixture.sh: no Docker,
# no network, no real staging.env touched) and checks its verdict. Exit status 0 = all cases passed.
set -uo pipefail

KIT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=fixture.sh
. "$KIT/tests/fixture.sh"

# 1. the scripts parse under this bash
if "$SHELL_UNDER_TEST" -n "$KIT/preflight.sh" && "$SHELL_UNDER_TEST" -n "$KIT/staging.sh"; then pass "scripts parse"
else flunk "scripts parse"; fi

# 2. every documented setting is allowed, with the Mac's existing subnet already used by this stack: kept, not recreated
write_env; write_config external; reset_state; own_network 10.253.247.0/24; other_network 10.213.47.0/24
run_preflight
expect "allowed settings + existing STAGING_SUBNET 10.253.247.0/24 (no network recreation)" 0 \
  "only staging settings in staging.env" "dedicated subnet 10.253.247.0/24 overlaps no other" \
  "existing network erpx-cf-staging_default is on 10.253.247.0/24 and is kept as it is (no recreation)" \
  "is external: Compose never recreates or removes it" "preflight: all checks passed"

# 3. optional settings documented as comments in staging.env.example are allowed too
write_env; printf 'STAGING_MINIO_IMAGE=pgsty/minio:RELEASE.2026-08-04T00-00-00Z\nSTAGING_CASHFREE_KEY_CHECK=relaxed\n' >> "$ENVF"
run_preflight
expect "optional documented settings" 0 "only staging settings in staging.env"

# 4. unexpected variables are refused, each named
write_env; printf 'DATABASE_URL=postgresql://x@y/z\nSTAGING_FOO=bar\n' >> "$ENVF"
run_preflight
expect "unexpected variables refused" 1 "unexpected settings in staging.env" "DATABASE_URL" "STAGING_FOO"

# 5. CRLF line endings: keys still recognised, values read, a warning shown
write_env; awk '{ printf "%s\r\n", $0 }' "$ENVF" > "$ENVF.crlf" && mv "$ENVF.crlf" "$ENVF"
run_preflight
expect "CRLF line endings" 0 "Windows line endings" "only staging settings in staging.env" "dedicated subnet 10.253.247.0/24"

# 6. a last line without a newline is still checked
write_env; printf 'STAGING_FOO=bar' >> "$ENVF"
run_preflight
expect "last line without newline" 1 "STAGING_FOO"

# 7. this stack's network on a different subnet than STAGING_SUBNET is still refused (validation kept)
write_env; reset_state; own_network 172.30.9.0/24
run_preflight
expect "existing network on another subnet refused" 1 "uses 172.30.9.0/24, not 10.253.247.0/24" "STAGING_SUBNET=172.30.9.0/24"

# 8. overlap with another Docker network is still refused
write_env; reset_state; other_network 10.253.0.0/16
run_preflight
expect "overlap with another network refused" 1 "overlaps: other(10.253.0.0/16)"

# 9. a malformed STAGING_SUBNET is refused
write_env; awk '{ sub(/^STAGING_SUBNET=.*/, "STAGING_SUBNET=10.253.247.0/8"); print }' "$ENVF" > "$ENVF.tmp" && mv "$ENVF.tmp" "$ENVF"
reset_state
run_preflight
expect "malformed subnet refused" 1 "must be an IPv4 network from /16 to /28"

# 10. a shell variable that would override staging.env is still refused
write_env; reset_state
env "${CLEAR[@]}" JWT_SECRET_KEY=from-the-shell PATH="$WORK/bin:$PATH" \
  "$SHELL_UNDER_TEST" "$REPO/ops/staging-cashfree/preflight.sh" > "$WORK/out.txt" 2>&1
echo $? > "$WORK/status.txt"
expect "shell override refused" 1 "these shell variables would override staging.env" "JWT_SECRET_KEY"

# 11. no staging network yet (first start): fine, ./staging.sh will create it
write_env; write_config external; reset_state
run_preflight
expect "no network yet is fine" 0 "network erpx-cf-staging_default does not exist yet: ./staging.sh creates it on 10.253.247.0/24"

# 12. a compose.yml that lets Compose manage the network is refused (this is what broke `up --force-recreate api`)
write_env; write_config managed; reset_state; own_network 10.253.247.0/24
run_preflight
expect "Compose-managed network refused" 1 "compose.yml must declare the default network external" "compose.yml must not define ipam"

# 13. the real compose.yml in this checkout declares the network the way preflight requires (guards the file itself)
if grep -qE '^    external: true$' "$KIT/compose.yml" && grep -qE '^    name: erpx-cf-staging_default$' "$KIT/compose.yml" \
   && ! awk '/^networks:/ { n = 1; next } /^[A-Za-z]/ { n = 0 } n && /^ +ipam:/ { f = 1 } END { exit !f }' "$KIT/compose.yml"; then
  pass "compose.yml declares erpx-cf-staging_default external, without ipam"
else flunk "compose.yml declares erpx-cf-staging_default external, without ipam"; fi

summary
