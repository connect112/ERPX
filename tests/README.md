# ERPX Test Suite

## Layout

- `tests/unit/` — pure logic, no database or network. Must run with nothing but `pip install -r apps/api/requirements.txt`.
- `tests/api/` — end-to-end tests against the FastAPI app via `httpx.AsyncClient` + `ASGITransport`, backed by a real transactional Postgres session per test.
- `tests/integration/` — like `tests/api`, but exercising multiple modules together (e.g. Accounting's Ledger + Journals + Invoices posting path).
- `tests/security/` — targeted tests asserting a specific security control holds (e.g. no information leakage on failed login).
- `tests/performance/` — latency-regression tests (`test_endpoint_latency.py`, in-process via the same `httpx`/`ASGITransport` setup as `tests/api`) plus `locustfile.py`, a real-HTTP load test against a running API server. See "Performance testing" below.
- `apps/web/e2e/` — browser-driven end-to-end tests (Playwright/TypeScript), colocated with the frontend they drive rather than under this Python `tests/` tree. See "End-to-end testing" below.

Fixtures that touch the database live in `tests/_fixtures.py`, pulled in by `tests/api/conftest.py`, `tests/integration/conftest.py`, `tests/security/conftest.py`, and `tests/performance/conftest.py` — never by the root `tests/conftest.py`, so `tests/unit` never needs a live database or even a constructible SQLAlchemy engine.

## Running locally

1. Start Postgres and Redis (`docker compose up -d postgres redis` from the repo root, or run them any other way).
2. Create the test database and apply migrations:
   ```bash
   createdb erpx_test
   cd apps/api
   DATABASE_URL=postgresql+asyncpg://erpx:erpx_secret@localhost:5432/erpx_test alembic upgrade head
   cd ../..
   ```
3. From the repo root:
   ```bash
   pip install -r apps/api/requirements.txt
   DATABASE_URL=postgresql+asyncpg://erpx:erpx_secret@localhost:5432/erpx_test pytest
   ```

Unit tests alone need none of the above:

```bash
pytest tests/unit
```

## Isolation model

Every `tests/api` / `tests/integration` test gets its own database transaction (`db_session` fixture) that is rolled back when the test ends. The app's `get_db` dependency is overridden so every request made through the `client` fixture during a test shares that same transaction — application code never calls `commit()` (only `flush()`, per `app/db/session.py`), so nothing behaves differently than it would in production, and no test can leak state into another.

## Markers

- `@pytest.mark.unit` — no database.
- `@pytest.mark.api` — hits the app via HTTP.
- `@pytest.mark.integration` — spans multiple modules.
- `@pytest.mark.security` — asserts a specific security control.
- `@pytest.mark.performance` — asserts a response-time budget.

## End-to-end testing (Playwright)

`apps/web/e2e/` drives a real Chromium browser against a real Vite dev server and a real FastAPI backend, both talking to the same Postgres instance as the rest of this suite.

```bash
cd apps/web
npx playwright install chromium   # once
npx playwright test
```

`playwright.config.ts` starts both the frontend (`npm run dev`) and backend (`uvicorn`) for you via its `webServer` config. `e2e/global-setup.ts` waits for the backend to become healthy, runs `apps/api/scripts/seed_e2e.py` (idempotent — creates an organization, a verified superuser, and RBAC if they don't already exist), logs in once through the real UI, and saves the resulting session so most specs start already authenticated. `e2e/auth.spec.ts` explicitly starts unauthenticated to exercise the login flow itself.

Override `E2E_DATABASE_URL` / `E2E_JWT_SECRET_KEY` env vars if your local Postgres isn't at the default `postgresql+asyncpg://erpx:erpx_secret@127.0.0.1:5433/erpx`.

## Performance testing

`tests/performance/test_endpoint_latency.py` runs alongside the rest of the pytest suite (`pytest tests/performance` or `pytest -m performance`) and asserts generous mean/max latency budgets on representative endpoints, using the same in-process `httpx`/`ASGITransport` client as `tests/api` — no network hop, so it's really catching backend-side regressions (N+1 queries, missing indexes) rather than measuring real-world latency.

`tests/performance/locustfile.py` is a genuine load test that needs a running API server reachable over real HTTP:

```bash
cd apps/api
DATABASE_URL=postgresql+asyncpg://erpx:erpx_secret@127.0.0.1:5433/erpx python -m scripts.seed_e2e
DATABASE_URL=postgresql+asyncpg://erpx:erpx_secret@127.0.0.1:5433/erpx uvicorn app.main:app --port 8000 &

cd ../..
locust -f tests/performance/locustfile.py --host http://127.0.0.1:8000 \
    --headless --users 10 --spawn-rate 2 --run-time 30s
```

Or drop `--headless` for the interactive web UI at `http://localhost:8089`. Requires `pip install locust` (not in `apps/api/requirements.txt` — it's a dev-only load-testing tool, not an app dependency).
