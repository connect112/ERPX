# ERPX — Windows (Podman + WSL2) Runbook

Operational guide for running ERPX locally on Windows with Podman 5.x + WSL2.
For architecture and module docs see the main `README.md`.

## TL;DR — after a reboot or "Cannot connect to Podman"

```powershell
.\start-erpx.ps1
```

That one script is idempotent — run it any time. It ensures the Podman machine
is up, starts every container in dependency order, waits for the API to answer,
launches the web dev server if it isn't already running, and prints the access
URLs. Then open:

- Web app  → http://localhost:5173
- API docs → http://localhost:8000/api/docs
- Login    → `admin@erpx.example.com` / `Admin@12345`

---

## Why a reboot breaks things (and what recovers each layer)

The stack has three layers with different restart behavior:

| Layer | What it is | Survives reboot? | Recovered by |
|-------|-----------|------------------|--------------|
| Podman **machine** | The WSL2 VM that hosts the container engine | ❌ Not auto-started on Windows login | `podman machine start` (in the script) |
| **Containers** | postgres, redis, minio, elasticsearch, api, celery ×2 | ⚠️ Only once the machine is up (`restart: unless-stopped`) | `podman start …` (in the script) |
| **Web frontend** | `npm run dev` (Vite) — a **native host process**, not a container | ❌ Dies with its terminal / on reboot | `npm run dev` (in the script) |

Because the machine and the native web process do **not** come back on their own,
`start-erpx.ps1` exists to bring all three back with one command.

> **"Cannot connect to Podman"** is usually not a crash — WSL2 has just gone to
> sleep and the API socket is cold. The first `podman` command wakes it. The
> script handles this automatically.

---

## Optional: auto-start the stack at login (no admin needed)

If you want the stack to come up automatically when you log in, add a shortcut
to your per-user Startup folder (this does **not** require administrator rights):

1. Press `Win + R`, type `shell:startup`, press Enter. A folder opens.
2. Create a new shortcut in it with this target:
   ```
   powershell.exe -ExecutionPolicy Bypass -File "C:\Users\MSDC-KLB61\Desktop\ERPX\start-erpx.ps1"
   ```
3. Name it `Start ERPX`.

At the next login it runs the recovery script automatically. Remove the shortcut
to disable. (Claude can create this shortcut for you on request.)

---

## Line endings — do not let CRLF come back

The original blocker on this machine was `core.autocrlf=true` rewriting the
POSIX shell scripts (`entrypoint.sh`, etc.) to CRLF on checkout, which made
`dash` inside the Linux containers fail with `set: Illegal option -` and
crash-loop every app container.

This is now prevented at two levels:

- **Repo-wide, for every developer:** `.gitattributes` pins `*.sh`, `Dockerfile`,
  and compose/YAML files to `eol=lf` regardless of anyone's git config.
- **This machine:** `core.autocrlf` is set to `false`.

If you ever hand-edit a `.sh` file with an editor that saves CRLF, fix it with:
```powershell
$f = "apps/api/scripts/entrypoint.sh"
[IO.File]::WriteAllText($f, ([IO.File]::ReadAllText($f) -replace "`r`n","`n"), (New-Object Text.UTF8Encoding($false)))
```

---

## Running the backend test suite

Tests live in the repo-root `tests/` directory and need a dedicated `erpx_test`
database (they are **not** bind-mounted into the container by default):

```powershell
$T = "postgresql+asyncpg://erpx:erpx_secret_change_me@postgres:5432/erpx_test"
podman exec erpx_postgres psql -U erpx -d erpx -c "CREATE DATABASE erpx_test;"
podman exec -e DATABASE_URL="$T" -w /app erpx_api alembic upgrade head
podman cp tests erpx_api:/app/tests
podman cp pytest.ini erpx_api:/app/pytest.ini
podman exec -e DATABASE_URL="$T" -w /app erpx_api python -m pytest tests -q -p no:cacheprovider
```

Current status: **314 / 315 pass**. The single failure
(`test_connection_test_records_real_success`) is environmental — it expects a
service on the container's own `127.0.0.1:9000`, which only holds on the host /
CI, not inside the API container. It is not a product defect.

> Note: `podman cp … erpx_api:/app/tests` writes through the `./apps/api:/app`
> bind-mount and therefore lands on the host at `apps/api/tests`. Delete that
> stray copy afterwards (the canonical tests live at the repo root) so it does
> not pollute the working tree or future image builds.

---

## Known local-setup notes

- **nginx is intentionally not run locally.** Its config proxies to `web:5173`
  inside the Podman network, which is unreachable when the web dev server runs
  natively on the host. Access the web app (`:5173`) and API (`:8000`) directly.
- **postgres is exposed on host port 5434** as well as 5432
  (`docker-compose.override.yml`) to avoid a clash with any native Windows
  PostgreSQL. Containers still talk to it internally as `postgres:5432`.
- **`docker-compose.local.yml`** pins the api/celery services to the pre-built
  `localhost/erpx-api:latest` image, working around podman-compose 1.6.0's
  Dockerfile-path bug on Windows. Start with `--no-build`.

---

## Quick command reference

```powershell
# Full recovery (idempotent)
.\start-erpx.ps1

# Status / logs
podman ps
podman logs erpx_api --tail 50
podman logs erpx_celery_worker --tail 50

# Stop everything (containers stay defined; machine keeps running)
podman stop erpx_api erpx_celery_worker erpx_celery_beat erpx_postgres erpx_redis erpx_minio erpx_elasticsearch

# Stop the whole VM (frees RAM)
podman machine stop
```
