# Built from the REPOSITORY ROOT as the build context (see docker-compose.yml
# and .github/workflows/docker-publish.yml), because the application code is
# split across `apps/api/` (the `app` package, alembic, scripts) and the
# repo-root `modules/` and `packages/` packages — all three must be baked in for
# the image to run without the dev bind-mounts. Build with:
#   docker build -f apps/api/Dockerfile .

# ---- Builder stage: compiles/installs dependencies into a venv ----
# build-essential and libpq-dev are only needed here (to build any wheel that
# doesn't ship a prebuilt manylinux binary) — kept out of the final image.
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Trust any extra CA cert(s) dropped into docker/extra-ca-certs/ (gitignored,
# empty by default — see that directory's own .gitignore) before installing
# from PyPI. This exists for networks where outbound HTTPS is transparently
# re-signed by a local TLS-inspecting proxy (corporate MITM proxy, or an
# antivirus "web shield" — e.g. Avast generates its own root CA and
# re-signs every HTTPS cert your traffic touches, including pip's, which a
# stock container has no reason to trust): `pip install` then fails with
# "SSLCertVerificationError: unable to get local issuer certificate",
# because the presented chain terminates in a root the image doesn't know.
# Copying an *empty* directory and running update-ca-certificates over it
# is a documented, safe no-op — every build with nothing dropped there
# (CI, any machine without this kind of interception) trusts exactly the
# same certs as before, byte for byte. This never disables or weakens
# certificate verification: an added CA is trusted explicitly for what a
# real proxy on this specific network actually presents, not "skip
# checking."
COPY docker/extra-ca-certs/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage: only what's needed to run the app ----
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# curl is needed by the HEALTHCHECK below; postgresql-client provides pg_dump,
# used by the scheduled database-backup task (modules/backups). The slim base
# (Debian trixie) ships pg_dump 17, which dumps the PostgreSQL 16 server
# (pg_dump is forward-compatible: client version must be >= server version). No
# compilers/dev headers ship in this stage. Runs as a non-root user rather than
# the container default (root).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system erpx && useradd --system --gid erpx --create-home --home-dir /home/erpx erpx

COPY --from=builder /opt/venv /opt/venv

# app package + alembic + scripts live under apps/api; modules/ and packages/
# live at the repo root. Copy all three so the image is self-contained (the
# empty apps/api/{modules,packages} bind-mount stubs are overwritten by the real
# trees copied next).
COPY --chown=erpx:erpx apps/api/ ./
COPY --chown=erpx:erpx modules/ ./modules/
COPY --chown=erpx:erpx packages/ ./packages/

USER erpx

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# The entrypoint applies migrations + the idempotent seed when RUN_MIGRATIONS is
# set (see scripts/entrypoint.sh), then execs the CMD (or the compose/K8s command
# override). Invoked via `sh` so it works regardless of the file's exec bit.
ENTRYPOINT ["sh", "/app/scripts/entrypoint.sh"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
