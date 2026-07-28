import { expect, test } from "@playwright/test";

const E2E_EMAIL = "e2e@erpx.example.com";
const E2E_PASSWORD = "E2ePass123!";

// Global setup already produced an authenticated storage state for every
// other spec; this file exercises the login flow itself, so it must start
// with a clean, unauthenticated session.
test.use({ storageState: { cookies: [], origins: [] } });

test("redirects unauthenticated visitors to /login", async ({ page }) => {
  await page.goto("/");
  await page.waitForURL("**/login");
  await expect(page.getByRole("heading", { name: "Sign in to ERPX" })).toBeVisible();
});

test("rejects an incorrect password", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_EMAIL);
  await page.getByLabel("Password").fill("WrongPassword123!");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByText(/invalid|incorrect|credentials/i)).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(/\/login$/);
});

test("logs in with valid credentials and reaches the dashboard", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(E2E_EMAIL);
  await page.getByLabel("Password").fill(E2E_PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();

  await page.waitForURL("http://localhost:5173/", { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: /Welcome back/ })).toBeVisible();
});
