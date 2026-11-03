#!/usr/bin/env bash
# Shared fixture for the staging script tests (sourced by preflight_test.sh and upgrade_test.sh; not run on its own).
# Needs KIT (the ops/staging-cashfree directory) and `set -uo pipefail` in the caller. Works on macOS bash 3.2.
#
# Every case runs the real preflight.sh / staging.sh in a throwaway git repository, with a fake `docker`, `curl` and
# `sleep` first on PATH: no Docker, no network, no real staging.env and no real container is ever touched.
#
# The fake docker is STATEFUL (files under $FAKE_STATE): one staging network with its subnet, attached containers,
# owner label and Compose "config hash", one other network, and whether the API container is running. Its `compose up`
# models what Compose 2.40+ does with a network it manages (pkg/compose/create.go, resolveOrCreateNetwork): when the
# hash stored on the network differs from the hash of the definition, it stops the selected services, tries to remove
# the network and fails while other containers are still attached. A network declared `external` is only looked up.

SHELL_UNDER_TEST="${BASH:-bash}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/staging-test.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
PASSED=0
FAILED=0
PROBLEMS=""
FAKE_STATE="$WORK/state"
FAKE_CONFIG="$WORK/config.yml"
export FAKE_STATE FAKE_CONFIG
mkdir -p "$FAKE_STATE" "$WORK/bin"

echo "bash under test: $SHELL_UNDER_TEST ($("$SHELL_UNDER_TEST" -c 'echo $BASH_VERSION'))"

# --- a throwaway repository holding the kit, like the real checkout
REPO="$WORK/repo"
mkdir -p "$REPO/ops/staging-cashfree"
for f in preflight.sh staging.sh staging.env.example compose.yml evidence.sql recon.sql .gitignore; do
  cp "$KIT/$f" "$REPO/ops/staging-cashfree/"
done
cp -R "$KIT/gate-templates" "$REPO/ops/staging-cashfree/"
(cd "$REPO" && git init -q && git add -A && git -c user.name=test -c user.email=test@example.com commit -qm fixture)
ENVF="$REPO/ops/staging-cashfree/staging.env"
NETNAME="erpx-cf-staging_default"
STACK_MEMBERS="erpx-cf-staging-postgres-1 erpx-cf-staging-redis-1 erpx-cf-staging-minio-1 erpx-cf-staging-mailpit-1 erpx-cf-staging-api-1 erpx-cf-staging-celery_worker-1 erpx-cf-staging-celery_beat-1 erpx-cf-staging-web-1 erpx-cf-staging-gateway-1 erpx-cf-staging-tunnel-1"

# --- fake docker (POSIX sh)
cat > "$WORK/bin/docker" <<'FAKE'
#!/bin/sh
S="$FAKE_STATE"
NETNAME=erpx-cf-staging_default
echo "docker $*" >> "$S/log"

which_net() {  # a name or id -> own | other | bridge (nothing when there is no such network)
  case "$1" in
    "$NETNAME"|own) [ -f "$S/net_subnet" ] && echo own ;;
    other) [ -f "$S/other_subnet" ] && echo other ;;
    bridge) echo bridge ;;
  esac
}
net_field() {  # <network> <--format string>
  case "$2" in
    *Containers*) [ "$1" = own ] && cat "$S/net_members" ;;
    *Labels*) [ "$1" = own ] && cat "$S/net_project" ;;
    *IPAM*) case "$1" in own) cat "$S/net_subnet" ;; other) cat "$S/other_subnet" ;; bridge) echo 172.17.0.0/16 ;; esac ;;
    *Name*) case "$1" in own) echo "$NETNAME" ;; *) echo "$1" ;; esac ;;
    *ID*) echo "$1" ;;
  esac
}

case "$1" in
  info) [ "${2:-}" = "--format" ] && echo 8000000000; exit 0 ;;
  ps) exit 0 ;;
  network)
    case "$2" in
      ls) [ -f "$S/net_subnet" ] && echo own; [ -f "$S/other_subnet" ] && echo other; echo bridge; exit 0 ;;
      inspect)
        target="$3"; fmt=""; shift 3
        while [ $# -gt 0 ]; do [ "$1" = "--format" ] && fmt="$2"; shift; done
        net="$(which_net "$target")"
        [ -n "$net" ] || { echo "Error: No such network: $target" >&2; exit 1; }
        [ -n "$fmt" ] && net_field "$net" "$fmt"
        exit 0 ;;
      create)
        shift 2; subnet=""; project=""; name=""
        while [ $# -gt 0 ]; do
          case "$1" in
            --subnet) subnet="$2"; shift 2 ;;
            --label) case "$2" in com.docker.compose.project=*) project="${2#*=}" ;; esac; shift 2 ;;
            --driver) shift 2 ;;
            *) name="$1"; shift ;;
          esac
        done
        [ -f "$S/net_subnet" ] && { echo "Error: network with name $name already exists" >&2; exit 1; }
        echo "$subnet" > "$S/net_subnet"; echo "$project" > "$S/net_project"; : > "$S/net_members"; echo match > "$S/net_hash"
        echo fakenetworkid; exit 0 ;;
      rm)
        [ -f "$S/net_subnet" ] || { echo "Error: No such network: $3" >&2; exit 1; }
        if [ -n "$(tr -d ' \n' < "$S/net_members")" ]; then
          echo "Error response from daemon: error while removing network: network $3 has active endpoints" >&2; exit 1
        fi
        rm -f "$S/net_subnet" "$S/net_members" "$S/net_project" "$S/net_hash"; echo "$3"; exit 0 ;;
    esac
    exit 0 ;;
  compose)
    [ "${2:-}" = "version" ] && { echo 2.40.0; exit 0; }
    shift; envfile=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --project-directory|-f|--profile) shift 2 ;;
        --env-file) envfile="$2"; shift 2 ;;
        *) break ;;
      esac
    done
    verb="$1"; shift
    case "$verb" in
      config) cat "$FAKE_CONFIG"; exit 0 ;;
      logs)
        case "$*" in
          *gateway*) cat "$S/gateway_log" 2>/dev/null ;;
          *celery_beat*) cat "$S/beat_log" 2>/dev/null ;;
          *celery_worker*) cat "$S/worker_log" 2>/dev/null ;;
          *) echo "tunnel-1  | https://new-name-5678.trycloudflare.com" ;;
        esac
        exit 0 ;;
      stop) for a in "$@"; do case "$a" in -*) ;; *) echo stopped > "$S/svc_$a" ;; esac; done; exit 0 ;;
      start) [ -n "${FAKE_START_FAILS:-}" ] && exit 1; for a in "$@"; do case "$a" in -*) ;; *) echo running > "$S/svc_$a" ;; esac; done; exit 0 ;;
      restart) echo restarted >> "$S/restarts"; exit 0 ;;
      ps) for a in "$@"; do case "$a" in -*|"{{.State}}") ;; *) cat "$S/svc_$a" 2>/dev/null; break ;; esac; done; exit 0 ;;
      exec)
        case "$*" in
          *"printenv FRONTEND_URL"*) cat "$S/frontend_url" 2>/dev/null ;;
          *"nginx -t"*) echo "nginx -t" >> "$S/nginx_checks"; [ -e "$S/nginx_invalid" ] && exit 1 ;;
          *nginx*reload*) echo reloaded >> "$S/gateway_reloads" ;;
          *"-v app="*) cat "$S/recon_facts" 2>/dev/null ;;
          *"-tA -c"*) cat "$S/paid_count" 2>/dev/null || echo 0 ;;
          *"inspect registered"*) cat "$S/registered" 2>/dev/null || echo "-> celery@w: OK
    * internship_onboarding.reconcile_payments" ;;
          *psql*) printf '== CHECKS\nduplicate payments | 0\n== Cashfree\n' ;;
        esac
        exit 0 ;;
      down)
        [ -n "${FAKE_DOWN_KEEPS:-}" ] || { [ -f "$S/net_members" ] && : > "$S/net_members"; }
        for s in api celery_worker celery_beat; do echo stopped > "$S/svc_$s"; done
        exit 0 ;;
      up)
        services=""
        for a in "$@"; do case "$a" in -*) ;; *) services="$services $a" ;; esac; done
        [ -n "$services" ] || services=" api celery_worker celery_beat"
        external=no
        awk '/^networks:/ { n = 1; next } /^[A-Za-z]/ { n = 0 } n && /external: true/ { f = 1 } END { exit !f }' "$FAKE_CONFIG" && external=yes
        if [ "$external" = yes ]; then
          [ -f "$S/net_subnet" ] || { echo "network $NETNAME declared as external, but could not be found" >&2; exit 1; }
        elif [ -f "$S/net_subnet" ] && [ "$(cat "$S/net_hash")" = stale ]; then
          # Compose 2.40+: stored hash != hash of the definition -> stop the selected services, remove the network
          m=" $(cat "$S/net_members") "
          for s in $services; do
            echo stopped > "$S/svc_$s"
            m="$(echo "$m" | sed "s/ erpx-cf-staging-$s-1 / /")"
          done
          echo "$m" > "$S/net_members"
          if [ -n "$(echo "$m" | tr -d ' ')" ]; then
            echo "Network $NETNAME Error: network $NETNAME has active endpoints" >&2; exit 1
          fi
          rm -f "$S/net_subnet" "$S/net_members" "$S/net_project" "$S/net_hash"
        fi
        if [ ! -f "$S/net_subnet" ]; then  # a managed network that was absent or just removed is created from the definition
          sub="$(awk '/subnet:/ { print $NF }' "$FAKE_CONFIG")"
          echo "$sub" > "$S/net_subnet"; echo erpx-cf-staging > "$S/net_project"; : > "$S/net_members"; echo match > "$S/net_hash"
        fi
        url=""
        [ -n "$envfile" ] && url="$(awk -F= '$1 == "STAGING_PUBLIC_URL" { sub(/\r$/, "", $2); v = $2 } END { print v }' "$envfile")"
        for s in $services; do
          echo running > "$S/svc_$s"
          case " $(cat "$S/net_members") " in *" erpx-cf-staging-$s-1 "*) ;; *) printf '%s ' "erpx-cf-staging-$s-1" >> "$S/net_members" ;; esac
          [ "$s" = api ] && echo "$url" > "$S/frontend_url"
        done
        exit 0 ;;
    esac
    exit 0 ;;
esac
exit 0
FAKE

cat > "$WORK/bin/curl" <<'FAKE'
#!/bin/sh
case "$*" in
  *health/ready*) [ "$(cat "$FAKE_STATE/svc_api" 2>/dev/null)" = running ] || exit 22; exit 0 ;;
  *api/v1/messages*) if [ -f "$FAKE_STATE/mail_json" ]; then cat "$FAKE_STATE/mail_json"; else echo '{"messages":[{"ID":"m1","Subject":"Receipt RCPT-1"}]}'; fi; exit 0 ;;
  */message/*/raw*) echo "raw mail"; exit 0 ;;
esac
exit 0
FAKE
printf '#!/bin/sh\n[ -n "${FAKE_SLEEP:-}" ] && exec /bin/sleep "$FAKE_SLEEP"\nexit 0\n' > "$WORK/bin/sleep"
chmod +x "$WORK/bin/docker" "$WORK/bin/curl" "$WORK/bin/sleep"

# --- state helpers
reset_state() {  # an empty Docker: no staging network, no other network, API stopped
  rm -rf "$FAKE_STATE"; mkdir -p "$FAKE_STATE"; : > "$FAKE_STATE/log"
  for s in api celery_worker celery_beat; do echo stopped > "$FAKE_STATE/svc_$s"; done
}
own_network() {  # <subnet> [stale|match]: the staging network as a RUNNING stack has it (all containers attached)
  echo "$1" > "$FAKE_STATE/net_subnet"; echo "${2:-stale}" > "$FAKE_STATE/net_hash"; echo erpx-cf-staging > "$FAKE_STATE/net_project"
  echo "$STACK_MEMBERS" > "$FAKE_STATE/net_members"
  for s in api celery_worker celery_beat; do echo running > "$FAKE_STATE/svc_$s"; done
}
other_network() { echo "$1" > "$FAKE_STATE/other_subnet"; }
write_config() {  # external = what compose.yml renders now; managed = the older definition (ipam, Compose-managed)
  {
    echo "name: erpx-cf-staging"
    echo "services:"
    for svc in api celery_worker celery_beat; do
      printf '  %s:\n    environment:\n      CASHFREE_ENV: sandbox\n      CASHFREE_ALLOW_PRODUCTION: "false"\n      ENVIRONMENT: staging\n' "$svc"
    done
    for port in 18080 18025; do
      printf '  svc%s:\n    ports:\n      - mode: ingress\n        host_ip: 127.0.0.1\n        target: 80\n        published: "%s"\n' "$port" "$port"
    done
    echo "networks:"
    echo "  default:"
    echo "    name: $NETNAME"
    if [ "${1:-external}" = external ]; then echo "    external: true"
    else printf '    ipam:\n      config:\n        - subnet: 10.253.247.0/24\n'; fi
    printf 'volumes:\n  pgdata:\n'
  } > "$FAKE_CONFIG"
}

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
set_env_value() {  # KEY VALUE
  awk -v k="$1" -v v="$2" 'BEGIN { d = 0 } index($0, k "=") == 1 { print k "=" v; d = 1; next } { print } END { if (!d) print k "=" v }' "$ENVF" > "$ENVF.tmp" && mv "$ENVF.tmp" "$ENVF"
}

# every setting the scripts would treat as a shell override (all documented ones, plus the fixed Cashfree switches)
CLEAR=()
for k in $(awk '{ sub(/\r$/, "") } match($0, /^#?[ ]*[A-Z_][A-Z0-9_]*=/) { k = substr($0, RSTART, RLENGTH - 1); sub(/^#?[ ]*/, "", k); print k }' \
             "$KIT/staging.env.example") CASHFREE_ENV CASHFREE_ENABLED CASHFREE_ALLOW_PRODUCTION DATABASE_URL; do
  CLEAR+=(-u "$k")
done

# --- running a script under test
run_preflight() {
  env "${CLEAR[@]}" PATH="$WORK/bin:$PATH" "$SHELL_UNDER_TEST" "$REPO/ops/staging-cashfree/preflight.sh" > "$WORK/out.txt" 2>&1 < /dev/null
  echo $? > "$WORK/status.txt"
}
run_staging() {  # staging.sh <command> [args]; stdin is whatever the caller pipes in (nothing by default)
  env "${CLEAR[@]}" PATH="$WORK/bin:$PATH" "$SHELL_UNDER_TEST" "$REPO/ops/staging-cashfree/staging.sh" "$@" > "$WORK/out.txt" 2>&1
  echo $? > "$WORK/status.txt"
}

# --- assertions
need_log() { grep -qF -- "$1" "$FAKE_STATE/log" || PROBLEMS="$PROBLEMS
      docker was never asked: $1"; }
forbid_log() { if grep -qF -- "$1" "$FAKE_STATE/log"; then PROBLEMS="$PROBLEMS
      docker was asked, and must not be: $1"; fi; }
need_state() { [ "$(cat "$FAKE_STATE/$1" 2>/dev/null)" = "$2" ] || PROBLEMS="$PROBLEMS
      state $1 should be '$2', is '$(cat "$FAKE_STATE/$1" 2>/dev/null)'"; }
need_state_has() { grep -qF -- "$2" "$FAKE_STATE/$1" 2>/dev/null || PROBLEMS="$PROBLEMS
      state $1 should contain '$2'"; }
forbid_file() { [ ! -e "$FAKE_STATE/$1" ] || PROBLEMS="$PROBLEMS
      $1 exists and must not"; }
need_file() { [ -e "$FAKE_STATE/$1" ] || PROBLEMS="$PROBLEMS
      $1 is missing"; }
need_env_line() { grep -qxF -- "$1" "$ENVF" || PROBLEMS="$PROBLEMS
      staging.env lacks the line $(echo "$1" | cut -d= -f1)=..."; }

# expect <name> <exit status> <text that must appear in the output>... ; also fails on any shell error or problem noted above
expect() {
  local name="$1" want_status="$2" got_status ok=1 text
  shift 2
  got_status="$(cat "$WORK/status.txt")"
  [ "$got_status" = "$want_status" ] || ok=0
  for text in "$@"; do grep -qF -- "$text" "$WORK/out.txt" || { ok=0; PROBLEMS="$PROBLEMS
      output lacks: $text"; }; done
  if grep -qE "syntax error|unbound variable|command not found|bad substitution" "$WORK/out.txt"; then ok=0; fi
  [ -z "$PROBLEMS" ] || ok=0
  if [ "$ok" = 1 ]; then echo "PASS  $name"; PASSED=$((PASSED + 1))
  else
    echo "FAIL  $name (exit $got_status, wanted $want_status)"; sed 's/^/      /' "$WORK/out.txt"
    [ -z "$PROBLEMS" ] || echo "$PROBLEMS"
    FAILED=$((FAILED + 1))
  fi
  PROBLEMS=""
}
pass() { echo "PASS  $1"; PASSED=$((PASSED + 1)); }
flunk() { echo "FAIL  $1"; FAILED=$((FAILED + 1)); }
summary() { echo "$PASSED passed, $FAILED failed"; [ "$FAILED" -eq 0 ]; }
