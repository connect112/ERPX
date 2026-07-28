import { expect, test } from "@playwright/test";

const ROUTES: { path: string; heading: string }[] = [
  { path: "/", heading: "Welcome back" },
  { path: "/crm/leads", heading: "Leads" },
  { path: "/students", heading: "Students" },
  { path: "/courses", heading: "Courses" },
  { path: "/accounting/ledger", heading: "Chart of Accounts" },
  { path: "/employees", heading: "Employees" },
  { path: "/administration/users", heading: "Users" },
];

for (const { path, heading } of ROUTES) {
  test(`renders ${path} without console errors`, async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    await page.goto(path);
    await expect(page.getByRole("heading", { name: new RegExp(heading) }).first()).toBeVisible({
      timeout: 10_000,
    });

    expect(pageErrors, `uncaught page errors on ${path}`).toEqual([]);
    expect(consoleErrors, `console.error calls on ${path}`).toEqual([]);
  });
}
