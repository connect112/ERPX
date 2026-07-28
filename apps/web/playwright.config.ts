import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, devices } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../..");
const API_DIR = path.resolve(__dirname, "../api");

const DATABASE_URL =
  process.env.E2E_DATABASE_URL ?? "postgresql+asyncpg://erpx:erpx_secret@127.0.0.1:5433/erpx";
const JWT_SECRET_KEY =
  process.env.E2E_JWT_SECRET_KEY ?? "test_secret_key_at_least_32_characters_long";

/**
 * Drives a real Chromium browser against a real Vite dev server and a real
 * FastAPI backend (started below via `webServer`), both talking to the same
 * local Postgres cluster used by `tests/api`/`tests/integration`. Login
 * state is captured once in `e2e/global-setup.ts` and reused via
 * `storageState` so most specs start already authenticated.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  reporter: [["list"]],
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    storageState: path.resolve(__dirname, "./e2e/.auth/user.json"),
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "npm run dev",
      cwd: __dirname,
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: API_DIR,
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: true,
      timeout: 60_000,
      env: {
        DATABASE_URL,
        JWT_SECRET_KEY,
        ENVIRONMENT: "test",
        PYTHONPATH: REPO_ROOT,
      },
    },
  ],
});
