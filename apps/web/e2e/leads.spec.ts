import { expect, test } from "@playwright/test";

test("creates a lead via the sidebar nav and views it on the detail page", async ({ page }) => {
  const leadName = `E2E Lead ${Date.now()}`;

  await page.goto("/");
  await page.getByRole("link", { name: "Leads" }).click();
  await page.waitForURL("**/crm/leads");
  await expect(page.getByRole("heading", { name: "Leads" })).toBeVisible();

  await page.getByRole("button", { name: "New Lead" }).click();
  await expect(page.getByRole("heading", { name: "New lead" })).toBeVisible();

  await page.getByLabel("Full name").fill(leadName);
  await page.getByLabel("Email").fill("e2e.lead@erpx.example.com");
  await page.getByRole("button", { name: "Create lead" }).click();

  await expect(page.getByRole("heading", { name: "New lead" })).not.toBeVisible({
    timeout: 10_000,
  });

  const row = page.getByRole("row", { name: new RegExp(leadName) });
  await expect(row).toBeVisible({ timeout: 10_000 });

  await row.click();
  await page.waitForURL("**/crm/leads/*");
  await expect(page.getByRole("heading", { name: leadName })).toBeVisible();
});
