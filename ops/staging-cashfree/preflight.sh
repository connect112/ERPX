#!/usr/bin/env bash
# Safety checks for the Cashfree SANDBOX staging stack. Run by ./staging.sh before it starts anything; any FAIL stops it.
# Usage: preflight.sh [--before-tunnel]   (before the tunnel exists, the public URL is not required yet)
# Works with macOS's bash 3.2 and Linux. Prints names and verdicts only, never a secret value.
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$DIR/../.." && pwd)"
ENVF="$DIR/staging.env"
PROJECT="erpx-cf-staging"
BEFORE_TUNNEL="${1:-}"
FAILS=0

ok() { echo "OK    $1"; }
warn() { echo "WARN  $1"; }
fail() { echo "FAIL  $1"; FAILS=$((FAILS + 1)); }
getv() { awk -v k="$1" '{ sub(/\r$/, "") } index($0, k "=") == 1 { v = substr($0, length(k) + 2) } END { print v }' "$ENVF"; }

# The settings staging.env may hold are exactly the ones documented in staging.env.example (set or commented out), so
# a new documented setting never needs a second list here.
ALLOWED="$(awk '{ sub(/\r$/, "") } match($0, /^#?[ ]*[A-Z_][A-Z0-9_]*=/) { k = substr($0, RSTART, RLENGTH - 1); sub(/^#?[ ]*/, "", k); print k }' "$DIR/staging.env.example" | sort -u | tr '\n' ' ')"
SECRETS="CASHFREE_SECRET_KEY POSTGRES_PASSWORD MINIO_ROOT_PASSWORD JWT_SECRET_KEY SEED_SUPERADMIN_PASSWORD STAGING_ADMIN_PASSWORD"

echo "== tools and resources"
command -v docker >/dev/null && docker info >/dev/null 2>&1 && ok "Docker is running" || fail "Docker is not running (start Docker Desktop)"
CV="$(docker compose version --short 2>/dev/null | sed 's/^v//')"
case "$CV" in
  2.2[0-9]*|2.[3-9][0-9]*|[3-9].*) ok "Docker Compose $CV" ;;
  *) fail "Docker Compose v2.20 or newer is needed (found: ${CV:-none})" ;;
esac
for t in curl git openssl awk; do command -v "$t" >/dev/null || fail "$t is missing"; done
echo "      machine: $(uname -s) $(uname -m)"
MEM="$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)"
if [ "${MEM:-0}" -lt 4000000000 ]; then fail "Docker has less than 4 GB memory (Docker Desktop > Settings > Resources: 6 GB or more)"
elif [ "$MEM" -lt 6000000000 ]; then warn "Docker has less than 6 GB memory; builds may be slow"
else ok "Docker memory $((MEM / 1000000000)) GB"; fi
FREE_KB="$(df -k "$REPO" | awk 'NR==2 {print $4}')"
[ "${FREE_KB:-0}" -ge 15000000 ] && ok "disk space $((FREE_KB / 1000000)) GB free" || warn "less than 15 GB free disk (images + volumes need about 8-10 GB)"

echo "== staging.env"
if [ ! -f "$ENVF" ]; then fail "staging.env is missing: run ./staging.sh init"; echo "$FAILS check(s) failed"; exit 1; fi
chmod 600 "$ENVF"
(cd "$REPO" && git check-ignore -q "$ENVF") && ok "staging.env is git-ignored" || fail "staging.env is not git-ignored"
(cd "$REPO" && git ls-files --error-unmatch "$ENVF" >/dev/null 2>&1) && fail "staging.env is tracked by Git: remove it from the index" || ok "staging.env is not tracked"
[ -n "$ALLOWED" ] || fail "could not read the documented settings from staging.env.example"
# A plain loop at the top level: bash 3.2 (macOS /bin/bash) mis-parses a `case` inside $( ... ), so never put one there.
UNKNOWN=""
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%$'\r'}"                       # tolerate Windows line endings
  case "$line" in
    [A-Za-z_]*=*) key="${line%%=*}" ;;       # a setting: KEY=value
    *) continue ;;                           # comments, blank lines
  esac
  case "$key" in
    *[!A-Za-z0-9_]*) continue ;;             # not a variable name
  esac
  case " $ALLOWED " in
    *" $key "*) ;;                           # documented in staging.env.example
    *) UNKNOWN="$UNKNOWN $key" ;;
  esac
done < "$ENVF"
grep -q "$(printf '\r')" "$ENVF" && warn "staging.env has Windows line endings; they are ignored, but save it as plain text" || true
[ -z "$UNKNOWN" ] && ok "only staging settings in staging.env" || fail "unexpected settings in staging.env (copied from another environment?): $UNKNOWN"
if grep -qiE "pentrix\.in|girtechnologies|amazonaws\.com|rds\.|shared_postgres|erpx_minio|api\.cashfree\.com|/opt/erpx" "$ENVF"; then
  fail "staging.env mentions a production host or service"
else ok "no production hosts in staging.env"; fi

echo "== shell environment"
SHELL_OVERRIDES=""
for k in $ALLOWED CASHFREE_ENV CASHFREE_ENABLED CASHFREE_ALLOW_PRODUCTION DATABASE_URL; do
  if [ -n "$(printenv "$k" 2>/dev/null)" ]; then SHELL_OVERRIDES="$SHELL_OVERRIDES $k"; fi
done
[ -z "$SHELL_OVERRIDES" ] && ok "no shell variables override staging.env" || fail "these shell variables would override staging.env; unset them first:$SHELL_OVERRIDES"
[ -n "$(env | awk -F= '/^AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY|SESSION_TOKEN)=/ {print $1}')" ] \
  && warn "AWS credentials are set in this shell (they are not passed to the stack; consider unsetting them)" || ok "no AWS credentials in this shell"

echo "== Cashfree (sandbox only)"
APP_ID="$(getv CASHFREE_APP_ID)"; KEY="$(getv CASHFREE_SECRET_KEY)"
if [ -z "$APP_ID" ] || [ -z "$KEY" ]; then
  [ "$BEFORE_TUNNEL" = "--before-tunnel" ] && warn "sandbox keys not set yet (needed before ./staging.sh up)" || fail "CASHFREE_APP_ID / CASHFREE_SECRET_KEY are empty (Test-mode keys)"
else
  case "$KEY" in *_prod_*) fail "the secret key looks like a LIVE key: use Test-mode keys only" ;; esac
  case "$APP_ID|$KEY" in
    TEST*|*"|"*_test_*) ok "keys look like Cashfree Test-mode keys" ;;
    *) if [ "$(getv STAGING_CASHFREE_KEY_CHECK)" = "relaxed" ]; then warn "key format not recognised as Test mode (check relaxed in staging.env)"
       else fail "keys do not look like Test-mode keys (App ID starting TEST / secret containing _test_); see README"; fi ;;
  esac
fi

echo "== generated secrets"
for k in POSTGRES_PASSWORD MINIO_ROOT_PASSWORD SEED_SUPERADMIN_PASSWORD STAGING_ADMIN_PASSWORD; do
  [ "$(getv "$k" | tr -d '\n' | wc -c | tr -d ' ')" -ge 20 ] || fail "$k must be a long random value (run ./staging.sh init)"
done
[ "$(getv JWT_SECRET_KEY | tr -d '\n' | wc -c | tr -d ' ')" -ge 32 ] || fail "JWT_SECRET_KEY must be 32+ random characters"
case "$(getv SEED_SUPERADMIN_PASSWORD)$(getv STAGING_ADMIN_PASSWORD)" in *Admin@12345*|*changeme*|*password*) fail "a known default password is used" ;; esac
LEAKS=""
for k in $SECRETS CASHFREE_APP_ID; do
  v="$(getv "$k")"
  [ ${#v} -ge 8 ] || continue
  if (cd "$REPO" && { git grep -I -q -F -e "$v" -- . 2>/dev/null || git grep --cached -I -q -F -e "$v" -- . 2>/dev/null; }); then LEAKS="$LEAKS $k"; fi
done
[ -z "$LEAKS" ] && ok "no staging secret appears in any tracked or staged file" || fail "these values appear in tracked/staged files (leaked):$LEAKS"

echo "== public address"
URL="$(getv STAGING_PUBLIC_URL)"
if [ "$BEFORE_TUNNEL" = "--before-tunnel" ] && [ -z "$URL" ]; then ok "public address comes next (./staging.sh tunnel)"
else
  case "$URL" in
    https://*.trycloudflare.com) ok "public address is a temporary Cloudflare quick tunnel" ;;
    https://*) warn "public address is not a quick tunnel: make sure it points only at this staging stack" ;;
    *) fail "STAGING_PUBLIC_URL must be the https:// tunnel address (run ./staging.sh tunnel)" ;;
  esac
fi

echo "== dedicated Docker subnet"
# IPv4 CIDR helpers (bash 3.2 + awk; 64-bit shell arithmetic)
cidr_range() { awk -v c="$1" 'BEGIN { split(c, a, "/"); n = split(a[1], o, "."); m = (a[2] == "" ? 32 : a[2]) + 0
  ip = ((o[1] * 256 + o[2]) * 256 + o[3]) * 256 + o[4]; size = 2 ^ (32 - m); s = int(ip / size) * size; printf "%.0f %.0f\n", s, s + size - 1 }'; }
overlaps() { local s1 e1 s2 e2; read -r s1 e1 <<EOF2
$(cidr_range "$1")
EOF2
  read -r s2 e2 <<EOF2
$(cidr_range "$2")
EOF2
  [ "$s1" -le "$e2" ] && [ "$s2" -le "$e1" ]; }
SUBNET="$(getv STAGING_SUBNET)"
if ! echo "$SUBNET" | grep -qE '^([0-9]{1,3}\.){3}[0-9]{1,3}/(1[6-9]|2[0-8])$'; then
  fail "STAGING_SUBNET must be an IPv4 network from /16 to /28 (e.g. 10.213.47.0/24), got '${SUBNET}'"
elif ! { overlaps "$SUBNET" 10.0.0.0/8 || overlaps "$SUBNET" 172.16.0.0/12 || overlaps "$SUBNET" 192.168.0.0/16; }; then
  fail "STAGING_SUBNET must be a private range (10.x, 172.16-31.x, 192.168.x)"
else
  OWN="$(docker network ls -q --filter "label=com.docker.compose.project=$PROJECT" 2>/dev/null | tr '\n' ' ')"
  CLASH=""
  for net in $(docker network ls -q 2>/dev/null); do
    case " $OWN " in *" $net "*) continue ;; esac
    for other in $(docker network inspect "$net" --format '{{range .IPAM.Config}}{{.Subnet}} {{end}}' 2>/dev/null); do
      case "$other" in *:*) continue ;; esac   # IPv6
      overlaps "$SUBNET" "$other" && CLASH="$CLASH $(docker network inspect "$net" --format '{{.Name}}')($other)"
    done
  done
  # this computer's own addresses (LAN, VPN) and Docker Desktop's internal network
  ADDRS="$( (ifconfig 2>/dev/null || ip -4 -o addr 2>/dev/null) | grep -oE 'inet (addr:)?([0-9]{1,3}\.){3}[0-9]{1,3}' | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | grep -v '^127\.')"
  for a in $ADDRS; do overlaps "$SUBNET" "$a/32" && CLASH="$CLASH host-address($a)"; done
  overlaps "$SUBNET" 192.168.65.0/24 && CLASH="$CLASH docker-desktop-internal(192.168.65.0/24)"
  if [ -n "$CLASH" ]; then fail "STAGING_SUBNET $SUBNET overlaps:$CLASH; set STAGING_SUBNET to a private range that overlaps none of these"
  else ok "dedicated subnet $SUBNET overlaps no other Docker network, host address or Docker Desktop range"; fi
  if [ -n "$OWN" ]; then
    CURRENT="$(docker network inspect $OWN --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null | head -1)"
    [ -z "$CURRENT" ] || [ "$CURRENT" = "$SUBNET" ] || fail "this stack's network uses $CURRENT, not $SUBNET: run ./staging.sh recreate-network (keeps all data)"
  fi
fi

echo "== ports and Docker conflicts"
for p in "$(getv STAGING_HTTP_PORT)" "$(getv STAGING_MAIL_PORT)"; do
  [ -n "$p" ] || { fail "STAGING_HTTP_PORT / STAGING_MAIL_PORT must be set"; continue; }
  owner="$(docker ps --filter "publish=$p" --format '{{.Names}}' 2>/dev/null | head -1)"
  case "$owner" in
    "") if command -v lsof >/dev/null && lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then fail "port $p is used by another program on this computer"
        else ok "port $p is free"; fi ;;
    "$PROJECT"-*) ok "port $p is this staging stack's" ;;
    *) fail "port $p is published by another container ($owner)" ;;
  esac
done
CFG="$(docker compose --project-directory "$DIR" -f "$DIR/compose.yml" --env-file "$ENVF" --profile tunnel config 2>&1)" || { fail "docker compose config failed: $(echo "$CFG" | tail -1)"; CFG=""; }
if [ -n "$CFG" ]; then
  echo "$CFG" | grep -q "^name: $PROJECT$" && ok "project name $PROJECT (all names prefixed, no fixed container names)" || fail "unexpected project name"
  echo "$CFG" | grep -q "container_name:" && fail "a fixed container_name is set" || true
  PUB="$(echo "$CFG" | grep -c "published:")"; LOCAL="$(echo "$CFG" | grep -c "host_ip: 127.0.0.1")"
  [ "$PUB" -eq 2 ] && [ "$LOCAL" -eq "$PUB" ] && ok "only 2 ports published, both on 127.0.0.1 (gateway, Mailpit viewer)" || fail "unsafe port bindings: $PUB published, $LOCAL on 127.0.0.1"
  # (the rendered file also repeats the shared settings block once, so "at least 3")
  [ "$(echo "$CFG" | grep -c 'CASHFREE_ENV: sandbox')" -ge 3 ] && ! echo "$CFG" | grep -qE 'CASHFREE_ENV: (production|"production")|CASHFREE_ALLOW_PRODUCTION: "true"' \
    && ok "Cashfree sandbox-only in api, worker and beat" || fail "Cashfree is not sandbox-only in every backend service"
  [ "$(echo "$CFG" | grep -c 'ENVIRONMENT: staging')" -ge 3 ] && ok "ENVIRONMENT=staging in every backend service" || fail "ENVIRONMENT is not staging everywhere"
fi

echo
if [ "$FAILS" -gt 0 ]; then echo "preflight: $FAILS check(s) failed; nothing was started"; exit 1; fi
echo "preflight: all checks passed"
