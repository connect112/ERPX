# ---- Builder stage: compiles/installs dependencies into a venv ----
# build-essential and libpq-dev are only needed here (to build any wheel
# that doesn't ship a prebuilt manylinux binary) — kept out of the final
# image entirely, since this whole stage is discarded after the venv copy
# below.
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage: only what's needed to run the app ----
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# curl is needed by the HEALTHCHECK below; no compilers/dev headers ship
# in this stage. Runs as a non-root user rather than the container default
# (root), following standard container-hardening practice.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system erpx && useradd --system --gid erpx --create-home --home-dir /home/erpx erpx

COPY --from=builder /opt/venv /opt/venv
COPY --chown=erpx:erpx . .

USER erpx

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
