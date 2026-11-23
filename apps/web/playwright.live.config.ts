import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../..");
const API_DIR = path.resolve(__dirname, "../api");
// 8000 is the default, but another program may own it on a developer machine: E2E_API_PORT moves the backend and the three dev proxies together
const API_PORT = process.env.E2E_API_PORT ?? "8000";
const PROXY = { VITE_API_PROXY_TARGET: `http://localhost:${API_PORT}` };

const DATABASE_URL = process.env.E2E_DATABASE_URL ?? "postgresql+asyncpg://erpx:erpx_secret@127.0.0.1:5433/erpx";
const JWT_SECRET_KEY = process.env.E2E_JWT_SECRET_KEY ?? "test_secret_key_at_least_32_characters_long";

/**
 * LIVE end-to-end tests of the Learning integration: a real Chromium drives the real admin site, the real student portal and the real
 * trainer portal (three Vite dev servers), all talking to a real FastAPI backend and a real PostgreSQL database. Nothing is stubbed.
 * `e2e-live/global-setup.ts` seeds a complete cohort (`apps/api/scripts/seed_learning_e2e.py`) before the suite runs.
 *
 *   E2E_DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db  npx playwright test -c playwright.live.config.ts
 *
 * Use a scratch database that is migrated to head (`alembic upgrade head`): the seed is idempotent but the specs create records. Set
 * PW_CHANNEL=chrome to use an installed Google Chrome instead of Playwright's Chromium.
 */
export default defineConfig({
  testDir: "./e2e-live",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  globalSetup: "./e2e-live/global-setup.ts",
  use: { trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], channel: process.env.PW_CHANNEL || undefined } }],
  webServer: [
    {
      command: `python -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: API_DIR,
      url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
      reuseExistingServer: true,
      timeout: 90_000,
      env: { ...(process.env as Record<string, string>), DATABASE_URL, JWT_SECRET_KEY, ENVIRONMENT: "test", PYTHONPATH: REPO_ROOT },
    },
    { command: "npm run dev", cwd: __dirname, url: "http://localhost:5173", reuseExistingServer: true, timeout: 90_000, env: { ...(process.env as Record<string, string>), ...PROXY } },
    { command: "npm run dev", cwd: path.resolve(__dirname, "../student-portal"), url: "http://localhost:5174", reuseExistingServer: true, timeout: 90_000, env: { ...(process.env as Record<string, string>), ...PROXY } },
    { command: "npm run dev", cwd: path.resolve(__dirname, "../trainer-portal"), url: "http://localhost:5175", reuseExistingServer: true, timeout: 90_000, env: { ...(process.env as Record<string, string>), ...PROXY } },
  ],
});
