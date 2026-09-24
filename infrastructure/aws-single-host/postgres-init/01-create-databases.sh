#!/bin/sh
# Runs once, automatically, on the Postgres container's first boot
# (docker-entrypoint-initdb.d convention) — never on subsequent restarts,
# so it's safe to leave in place permanently. Creates two fully separate
# database + user pairs inside the one shared Postgres instance, one per
# app, so neither app can see or touch the other's data despite sharing a
# process. $POSTGRES_USER/$POSTGRES_PASSWORD here are the superuser the
# base postgres image itself creates from docker-compose.yml's own
# environment block — used only to run these CREATE statements, never used
# by either application.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER erpx WITH PASSWORD '${ERPX_DB_PASSWORD}';
    CREATE DATABASE erpx OWNER erpx;

    CREATE USER pentrix WITH PASSWORD '${PENTRIX_DB_PASSWORD}';
    CREATE DATABASE pentrix OWNER pentrix;
EOSQL
