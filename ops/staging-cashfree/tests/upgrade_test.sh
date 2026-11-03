#!/usr/bin/env bash
# Regression tests for upgrading an ALREADY-RUNNING staging stack with the current scripts and compose.yml:
#   /bin/bash ops/staging-cashfree/tests/upgrade_test.sh        (on macOS this is bash 3.2)
#
# The scenario that failed on the Mac: the network erpx-cf-staging_default exists (subnet 10.253.247.0/24), was created
# by an older compose.yml so the hash Compose stored on it differs from the current definition, and PostgreSQL, Redis,
# MinIO, Mailpit, the gateway, web and the tunnel are attached. `up -d --no-deps --force-recreate api` then made Compose
# stop the API and fail to remove the occupied network. Here staging.sh must restart only what it was asked to, never
# create, change or remove that network, and keep every data container attached. See fixture.sh for the fake Docker.
set -uo pipefail

KIT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=fixture.sh
. "$KIT/tests/fixture.sh"

NEW_URL="https://conviction-catering-providence-lifetime.trycloudflare.com"

# the running Mac stack: stale-hash network, everything attached, API running
running_stack() { write_env; write_config external; reset_state; own_network 10.253.247.0/24 stale; }
no_network_changes() { forbid_log "network rm"; forbid_log "network create"; forbid_log "compose --project-directory $REPO/ops/staging-cashfree -f $REPO/ops/staging-cashfree/compose.yml --env-file $ENVF down"; }

# 1. the new public URL reaches the API without touching the network or any data service
running_stack; set_env_value STAGING_PUBLIC_URL "$NEW_URL"
run_staging refresh-app
need_log "up -d --no-deps --force-recreate api celery_worker celery_beat"
no_network_changes
forbid_log " stop"
need_state svc_api running; need_state svc_celery_worker running; need_state svc_celery_beat running
need_state frontend_url "$NEW_URL"
need_state_has net_members "erpx-cf-staging-postgres-1"; need_state_has net_members "erpx-cf-staging-minio-1"
need_state_has net_members "erpx-cf-staging-mailpit-1"; need_state_has net_members "erpx-cf-staging-redis-1"
need_state_has net_subnet "10.253.247.0/24"
need_file gateway_reloads
expect "refresh-app on the running stack: new URL in api/worker/beat, network untouched" 0 \
  "restarting api, celery_worker, celery_beat" "gateway reloaded" "the API now uses FRONTEND_URL=$NEW_URL" "preflight: all checks passed"

# 2. the tunnel command starts only the tunnel and never touches the network
running_stack
run_staging tunnel
need_log "up -d --no-deps tunnel"
no_network_changes
forbid_log "force-recreate"
need_env_line "STAGING_PUBLIC_URL=https://new-name-5678.trycloudflare.com"
need_state svc_api running
need_state_has net_subnet "10.253.247.0/24"
expect "tunnel on the running stack: only the tunnel, network untouched, new address saved" 0 \
  "public address: https://new-name-5678.trycloudflare.com" "refresh-app"

# 3. a normal `up` on the running stack leaves the network alone as well
running_stack
run_staging up
need_log "up -d --build"
no_network_changes
need_state svc_api running
need_state_has net_members "erpx-cf-staging-postgres-1"
expect "up on the running stack: network untouched, data services attached" 0 "ready."

# 4. network-check is read-only and says why this is safe
running_stack
run_staging network-check
no_network_changes
forbid_log "compose --project-directory $REPO/ops/staging-cashfree -f $REPO/ops/staging-cashfree/compose.yml --env-file $ENVF --profile tunnel up"
expect "network-check (read-only) reports the existing network and that Compose will not recreate it" 0 \
  "subnet 10.253.247.0/24" "OK    subnet matches STAGING_SUBNET" "declares the network external"

# 5. first start on a clean Mac: the network is created once, on STAGING_SUBNET, labelled as this project's
write_env; write_config external; reset_state
run_staging tunnel
need_log "network create --driver bridge --subnet 10.253.247.0/24 --label com.docker.compose.project=erpx-cf-staging --label com.erpx.staging=sandbox erpx-cf-staging_default"
need_state net_project erpx-cf-staging
expect "first start creates the network on STAGING_SUBNET" 0 "created the network erpx-cf-staging_default on 10.253.247.0/24"
run_staging tunnel
n="$(grep -c "network create" "$FAKE_STATE/log")"
[ "$n" = 1 ] && pass "a second start does not create it again" || flunk "a second start created the network again ($n creates)"

# 6. the existing network on another subnet than STAGING_SUBNET: refused before anything is restarted
running_stack; own_network 172.30.9.0/24 stale; set_env_value STAGING_PUBLIC_URL "$NEW_URL"
run_staging refresh-app
no_network_changes
forbid_log " up "
need_state svc_api running
expect "subnet mismatch: refused, nothing restarted" 1 "uses 172.30.9.0/24, not 10.253.247.0/24" "STAGING_SUBNET=172.30.9.0/24"

# 7. a compose.yml that hands the network back to Compose is refused before anything is stopped
running_stack; write_config managed; set_env_value STAGING_PUBLIC_URL "$NEW_URL"
run_staging refresh-app
forbid_log " up "
no_network_changes
need_state svc_api running
expect "Compose-managed network definition refused before any restart" 1 "compose.yml must declare the default network external"

# 8. control: the fake Compose reproduces the Mac failure for a Compose-managed network with a stale hash...
running_stack; write_config managed
out="$(env PATH="$WORK/bin:$PATH" docker compose --project-directory . -f compose.yml --env-file "$ENVF" up -d --no-deps --force-recreate api 2>&1)"; st=$?
if [ "$st" != 0 ] && echo "$out" | grep -q "has active endpoints" && [ "$(cat "$FAKE_STATE/svc_api")" = stopped ]; then
  pass "control: a Compose-managed network with a stale hash stops the API and fails to remove the network (the Mac failure)"
else flunk "control: the fake Compose no longer reproduces the failure, so these tests would not catch a regression"; fi

# 9. ...and the same command against the external definition succeeds on the same network
running_stack; write_config external
out="$(env PATH="$WORK/bin:$PATH" docker compose --project-directory . -f compose.yml --env-file "$ENVF" up -d --no-deps --force-recreate api 2>&1)"; st=$?
if [ "$st" = 0 ] && [ "$(cat "$FAKE_STATE/svc_api")" = running ] && [ -f "$FAKE_STATE/net_subnet" ]; then
  pass "control: the external definition recreates the API on the same occupied network"
else flunk "control: the external definition did not recreate the API cleanly: $out"; fi

# 10. an external network that is missing is reported by Compose itself, nothing is created behind your back
write_env; write_config external; reset_state
out="$(env PATH="$WORK/bin:$PATH" docker compose --project-directory . -f compose.yml --env-file "$ENVF" up -d --no-deps tunnel 2>&1)"; st=$?
if [ "$st" != 0 ] && echo "$out" | grep -q "declared as external, but could not be found"; then pass "running Compose directly without the network fails clearly (use ./staging.sh)"
else flunk "running Compose directly without the network did not fail clearly"; fi

# 11. recreate-network (the one command that moves the subnet): evidence first, containers down, only then the empty network
running_stack; set_env_value STAGING_SUBNET 10.99.88.0/24
printf 'erpx-cf-staging\n' | run_staging recreate-network
need_log "network rm erpx-cf-staging_default"
forbid_log "--volumes"; forbid_log "volume rm"
forbid_file net_subnet
expect "recreate-network removes the emptied network and keeps the volumes" 0 "saved to" "removed the network erpx-cf-staging_default" "done (data kept)"
run_staging tunnel
need_log "network create --driver bridge --subnet 10.99.88.0/24"
expect "after recreate-network the next start creates the network on the new subnet" 0 "created the network erpx-cf-staging_default on 10.99.88.0/24"

# 12. the network is never removed while anything is still attached, or when it is not this project's
running_stack; set_env_value STAGING_SUBNET 10.99.88.0/24
printf 'erpx-cf-staging\n' | FAKE_DOWN_KEEPS=1 run_staging recreate-network
forbid_log "network rm"
need_file net_subnet
expect "a network still in use is not removed" 1 "not removing erpx-cf-staging_default: still in use by"
running_stack; echo some-other-project > "$FAKE_STATE/net_project"
printf 'erpx-cf-staging\n' | run_staging recreate-network
forbid_log "network rm"
need_file net_subnet
expect "a network that is not this project's is not removed" 1 "does not belong to project erpx-cf-staging"

summary
