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
    && rm -rf /var/lib/apt/lists/*

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

# curl is needed by the HEALTHCHECK below; no compilers/dev headers ship in this
# stage. Runs as a non-root user rather than the container default (root).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
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

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
