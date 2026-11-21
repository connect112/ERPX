import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const API_DIR = path.resolve(__dirname, "../../api");

/** Seeds the cohort the live Learning tests work on (idempotent). The backend itself is started by Playwright's `webServer`. */
export default async function globalSetup(): Promise<void> {
  const result = spawnSync("python", ["-m", "scripts.seed_learning_e2e"], {
    cwd: API_DIR,
    env: {
      ...process.env,
      DATABASE_URL: process.env.E2E_DATABASE_URL ?? "postgresql+asyncpg://erpx:erpx_secret@127.0.0.1:5433/erpx",
      JWT_SECRET_KEY: process.env.E2E_JWT_SECRET_KEY ?? "test_secret_key_at_least_32_characters_long",
      ENVIRONMENT: "test",
      PYTHONPATH: path.resolve(__dirname, "../../.."),
    },
    stdio: "inherit",
  });
  if (result.status !== 0) throw new Error(`seed_learning_e2e failed with exit code ${result.status}`);
}
