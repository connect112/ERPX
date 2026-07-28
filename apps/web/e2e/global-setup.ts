import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, type FullConfig } from "@playwright/test";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const API_DIR = path.resolve(__dirname, "../../api");
const AUTH_FILE = path.resolve(__dirname, ".auth/user.json");

const HEALTH_URL = "http://127.0.0.1:8000/api/v1/health";
const E2E_EMAIL = "e2e@erpx.example.com";
const E2E_PASSWORD = "E2ePass123!";

async function waitForHealth(timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(HEALTH_URL);
      if (res.ok) return;
    } catch {
      // backend not up yet — keep polling
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Backend at ${HEALTH_URL} did not become healthy within ${timeoutMs}ms`);
}

function seedDatabase(): void {
  const env = {
    ...process.env,
    DATABASE_URL:
      process.env.E2E_DATABASE_URL ?? "postgresql+asyncpg://erpx:erpx_secret@127.0.0.1:5433/erpx",
    JWT_SECRET_KEY: process.env.E2E_JWT_SECRET_KEY ?? "test_secret_key_at_least_32_characters_long",
    PYTHONPATH: path.resolve(__dirname, "../../.."),
  };

  const result = spawnSync("python", ["-m", "scripts.seed_e2e"], {
    cwd: API_DIR,
    env,
    stdio: "inherit",
  });

  if (result.status !== 0) {
    throw new Error(`seed_e2e.py failed with exit code ${result.status}`);
  }
}

export default async function globalSetup(config: FullConfig): Promise<void> {
  await waitForHealth(60_000);
  seedDatabase();

  const baseURL = config.projects[0]?.use.baseURL ?? "http://localhost:5173";
  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.goto(`${baseURL}/login`);
  await page.getByLabel("Email").fill(E2E_EMAIL);
  await page.getByLabel("Password").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(baseURL + "/", { timeout: 15_000 });

  await page.context().storageState({ path: AUTH_FILE });
  await browser.close();
}
