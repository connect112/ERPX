import { type Page, expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const roles = JSON.parse(readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "../src/components/navigation/role-permissions.fixture.json"), "utf8")) as { roles: Record<string, string[]> };

/**
 * The sidebar, its hover/keyboard/touch behaviour, its search and the role-based menus, in a real browser on the PRODUCTION build.
 * Only the JSON API is stubbed (as in the receipts suites), so no backend is needed.
 */

type Profile = { permissions: string[]; superuser?: boolean; trainer?: boolean; employee?: boolean; student?: boolean };
const PROFILES: Record<string, Profile> = {
  administrator: { permissions: roles.roles.administrator },
  staff: { permissions: roles.roles.staff },
  pentrix_staff: { permissions: roles.roles.pentrix_staff },
  super_admin: { permissions: [], superuser: true },
  trainer_only: { permissions: [], trainer: true },
  nobody: { permissions: [] },
};

const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });

async function signIn(page: Page, who: keyof typeof PROFILES = "administrator", storage: Record<string, string> = {}) {
  const prof = PROFILES[who];
  await page.addInitScript(
    ([store]) => {
      // only before the first load of the test: a reload must see what the page itself saved
      if (sessionStorage.getItem("__seeded")) return;
      sessionStorage.setItem("__seeded", "1");
      localStorage.setItem("erpx-auth", JSON.stringify({ state: { accessToken: "t", refreshToken: "r", isAuthenticated: true, user: { id: "u1", email: "a@example.com", fullName: "Test Admin", status: "active", isEmailVerified: true, twoFactorEnabled: false } }, version: 0 }));
      for (const [k, v] of Object.entries(store)) localStorage.setItem(k, v);
    },
    [storage] as const,
  );
  await page.route("**/api/v1/**", (route) => {
    const p = new URL(route.request().url()).pathname.replace(/^\/api\/v1/, "");
    if (p === "/authorization/me") return route.fulfill(json({ user_id: "u1", roles: [], effective_permissions: prof.permissions, is_superuser: !!prof.superuser }));
    if (p === "/trainers/me") return route.fulfill(prof.trainer ? json({ id: "t1" }) : json({ detail: "none" }, 404));
    if (p === "/employees/me") return route.fulfill(prof.employee ? json({ id: "e1" }) : json({ detail: "none" }, 404));
    if (p === "/students/me") return route.fulfill(prof.student ? json({ id: "s1" }) : json({ detail: "none" }, 404));
    if (p.startsWith("/notifications")) return route.fulfill(json({ items: [], total: 0, page: 1, page_size: 20, unread_count: 0, count: 0 }));
    return route.fulfill(json({ items: [], total: 0, detail: "stub" }, 404));
  });
}

const sidebar = (page: Page) => page.getByTestId("sidebar");
const slot = (page: Page) => page.getByTestId("nav-slot");
const mainLeft = (page: Page) => page.locator("main").evaluate((el) => el.getBoundingClientRect().left);
const widthOf = (page: Page) => sidebar(page).evaluate((el) => el.getBoundingClientRect().width);
const group = (page: Page, name: string) => sidebar(page).getByRole("button", { name, exact: true });
const modKey = process.platform === "darwin" ? "Meta" : "Control";

test.describe("desktop sidebar", () => {
  test.use({ viewport: { width: 1366, height: 768 } });

  test("starts pinned and expanded with the logo, a search box and collapsible groups", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await expect(sidebar(page)).toHaveAttribute("data-expanded", "true");
    await expect(slot(page)).toHaveAttribute("data-mode", "pinned");
    expect(await widthOf(page)).toBe(256);
    await expect(sidebar(page).getByText("ERPX", { exact: true })).toBeVisible();
    await expect(sidebar(page).getByPlaceholder("Search modules...")).toBeVisible();
    await expect(sidebar(page).getByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
    await expect(sidebar(page).getByRole("link", { name: "Calendar" })).toBeVisible();
    for (const g of ["Workspace", "Internships", "Students & Learning", "Events & Institutions", "Pentrix", "Marketing & Sales", "Careers & Alumni", "Communications", "People & HR", "Finance", "Operations & Assets", "Corporate", "Administration", "Platform"]) {
      await expect(group(page, g)).toHaveAttribute("aria-expanded", "false");
    }
  });

  test("groups open and close with a click, several can stay open, and the chevron follows", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await group(page, "Finance").click();
    await group(page, "Pentrix").click();
    await expect(group(page, "Finance")).toHaveAttribute("aria-expanded", "true");
    await expect(group(page, "Pentrix")).toHaveAttribute("aria-expanded", "true");
    await expect(sidebar(page).getByRole("link", { name: "Invoices" })).toBeVisible();
    await expect(sidebar(page).getByRole("link", { name: "Labs" })).toBeVisible();
    await group(page, "Finance").click();
    await expect(sidebar(page).getByRole("link", { name: "Invoices" })).toHaveCount(0);
    await expect(sidebar(page).getByRole("link", { name: "Labs" })).toBeVisible();
  });

  test("opens the group of the current page, highlights it, and remembers open groups after a reload", async ({ page }) => {
    await signIn(page);
    await page.goto("/accounting/invoices");
    await expect(group(page, "Finance")).toHaveAttribute("aria-expanded", "true");
    await expect(group(page, "Finance")).toHaveAttribute("data-active-group", "true");
    await expect(sidebar(page).getByRole("link", { name: "Invoices" })).toHaveAttribute("aria-current", "page");
    await group(page, "Communications").click();
    await page.reload();
    await expect(group(page, "Finance")).toHaveAttribute("aria-expanded", "true");
    await expect(group(page, "Communications")).toHaveAttribute("aria-expanded", "true");
    await expect(group(page, "Corporate")).toHaveAttribute("aria-expanded", "false");
  });

  test("collapses to a 64px icon rail that stays visible, with search and the toggle, and the page uses the freed space", async ({ page }) => {
    await signIn(page);
    await page.goto("/accounting/invoices");
    const pinnedLeft = await mainLeft(page);
    await page.getByRole("button", { name: "Collapse sidebar" }).click();
    await page.mouse.move(900, 400);
    await expect(slot(page)).toHaveAttribute("data-mode", "collapsed");
    await expect(sidebar(page)).toHaveAttribute("data-expanded", "false");
    await expect.poll(() => widthOf(page)).toBe(64);
    await expect.poll(() => mainLeft(page)).toBe(64);
    expect(pinnedLeft).toBe(256);
    await expect(sidebar(page).getByRole("button", { name: "Search modules" })).toBeVisible();
    await expect(sidebar(page).getByRole("button", { name: "Expand sidebar" })).toBeVisible();
    await expect(group(page, "Finance")).toHaveAttribute("data-active-group", "true"); // the active route is still marked in the rail
    await expect(page.getByPlaceholder("Search modules...")).toHaveCount(0);
  });

  test("hovering the rail opens the full sidebar over the page without moving it, and leaving folds it back", async ({ page }) => {
    await signIn(page, "administrator", { "erpx.nav.mode": "collapsed" });
    await page.goto("/accounting/invoices");
    await expect(slot(page)).toHaveAttribute("data-mode", "collapsed");
    const before = await page.locator("main").evaluate((el) => { const r = el.getBoundingClientRect(); return { left: r.left, width: r.width, top: r.top }; });
    await page.mouse.move(30, 300);
    await expect(sidebar(page)).toHaveAttribute("data-overlay", "true");
    await expect.poll(() => widthOf(page)).toBe(256);
    await expect(sidebar(page).getByPlaceholder("Search modules...")).toBeVisible();
    const during = await page.locator("main").evaluate((el) => { const r = el.getBoundingClientRect(); return { left: r.left, width: r.width, top: r.top }; });
    expect(during).toEqual(before); // nothing in the page shifted or resized
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    // the overlay is on top of the page
    const topmost = await page.evaluate(() => document.elementFromPoint(200, 300)?.closest("[data-testid='sidebar']") !== null);
    expect(topmost).toBe(true);
    // the saved choice is untouched by hovering
    expect(await page.evaluate(() => localStorage.getItem("erpx.nav.mode"))).toBe("collapsed");
    await page.mouse.move(900, 400);
    await expect(sidebar(page)).toHaveAttribute("data-overlay", "false");
    await expect.poll(() => widthOf(page)).toBe(64);
  });

  test("does not flicker when the pointer crosses the edge, and stays open while it is inside", async ({ page }) => {
    await signIn(page, "administrator", { "erpx.nav.mode": "collapsed" });
    await page.goto("/");
    await page.mouse.move(30, 300);
    await expect(sidebar(page)).toHaveAttribute("data-overlay", "true");
    const states: string[] = [];
    await page.exposeFunction("__record", (s: string) => states.push(s));
    await page.evaluate(() => {
      const el = document.querySelector("[data-testid='sidebar']")!;
      new MutationObserver(() => (window as unknown as { __record: (s: string) => void }).__record(el.getAttribute("data-overlay")!)).observe(el, { attributes: true, attributeFilter: ["data-overlay"] });
    });
    // wander across the overlay (past the rail width) and along its edge, then briefly out and back inside the grace period
    for (let x = 30; x < 250; x += 20) await page.mouse.move(x, 300);
    await page.mouse.move(255, 300);
    await page.mouse.move(258, 300);
    await page.mouse.move(250, 310);
    expect(states).toEqual([]);
    await expect(sidebar(page)).toHaveAttribute("data-overlay", "true");
  });

  test("the toggle pins it open, and that choice survives a reload; hovering afterwards never changes it", async ({ page }) => {
    await signIn(page, "administrator", { "erpx.nav.mode": "collapsed" });
    await page.goto("/");
    await page.mouse.move(30, 300);
    await sidebar(page).getByRole("button", { name: "Expand sidebar" }).click();
    await expect(slot(page)).toHaveAttribute("data-mode", "pinned");
    await expect.poll(() => mainLeft(page)).toBe(256);
    await page.mouse.move(900, 400);
    await expect(sidebar(page)).toHaveAttribute("data-expanded", "true"); // pinned stays open when the pointer leaves
    await page.reload();
    await expect(slot(page)).toHaveAttribute("data-mode", "pinned");
    await sidebar(page).getByRole("button", { name: "Collapse sidebar" }).click();
    await page.reload();
    await expect(slot(page)).toHaveAttribute("data-mode", "collapsed");
  });

  test("the rail's group icons open the overlay with that group already open (touch has no hover)", async ({ page }) => {
    await signIn(page, "administrator", { "erpx.nav.mode": "collapsed" });
    await page.goto("/");
    await group(page, "Finance").dispatchEvent("click");
    await expect(sidebar(page)).toHaveAttribute("data-overlay", "true");
    await expect(sidebar(page).getByRole("link", { name: "Invoices" })).toBeVisible();
    await page.locator("main").click({ position: { x: 600, y: 300 } }); // a tap elsewhere closes it
    await expect(sidebar(page)).toHaveAttribute("data-overlay", "false");
  });

  test("keyboard focus reveals the labels, Escape closes them and puts focus on the toggle", async ({ page }) => {
    await signIn(page, "administrator", { "erpx.nav.mode": "collapsed" });
    await page.goto("/");
    await page.mouse.move(900, 400);
    await sidebar(page).getByRole("button", { name: "Expand sidebar" }).focus();
    await page.keyboard.press("Tab"); // the search icon
    await page.keyboard.press("Tab"); // Dashboard
    await expect(sidebar(page)).toHaveAttribute("data-overlay", "true");
    await expect(sidebar(page).getByRole("link", { name: "Dashboard" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(sidebar(page)).toHaveAttribute("data-overlay", "false");
    await expect(sidebar(page).getByRole("button", { name: "Expand sidebar" })).toBeFocused();
    await expect(sidebar(page)).toHaveAttribute("data-overlay", "false"); // refocusing the toggle did not reopen it
  });

  test("the icon-only controls have accessible names", async ({ page }) => {
    await signIn(page, "administrator", { "erpx.nav.mode": "collapsed" });
    await page.goto("/");
    await page.mouse.move(900, 400);
    for (const name of ["Expand sidebar", "Search modules", "Finance", "Pentrix"]) await expect(sidebar(page).getByRole("button", { name, exact: true })).toBeVisible();
    await expect(sidebar(page).getByRole("link", { name: "Dashboard" })).toBeVisible();
  });

  test("reduced motion removes the width transition", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await signIn(page);
    await page.goto("/");
    expect(await sidebar(page).evaluate((el) => getComputedStyle(el).transitionProperty)).toBe("none");
    expect(await slot(page).evaluate((el) => getComputedStyle(el).transitionProperty)).toBe("none");
  });

  test("with motion allowed the overlay opens in about 200ms", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    const d = await sidebar(page).evaluate((el) => getComputedStyle(el).transitionDuration.split(",").map((s) => parseFloat(s) * 1000));
    expect(Math.max(...d)).toBeGreaterThanOrEqual(150);
    expect(Math.max(...d)).toBeLessThanOrEqual(200);
  });

  test("the page never scrolls sideways or as a whole, expanded or collapsed", async ({ page }) => {
    await signIn(page);
    for (const mode of ["pinned", "collapsed"] as const) {
      await page.addInitScript((m) => { try { if (!sessionStorage.getItem("__m")) localStorage.setItem("erpx.nav.mode", m); } catch { /* */ } }, mode);
      await page.goto("/");
      await page.evaluate((m) => localStorage.setItem("erpx.nav.mode", m), mode);
      await page.reload();
      const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, w: innerWidth, h: innerHeight }));
      expect(m.sw).toBeLessThanOrEqual(m.w);
      expect(m.sh).toBeLessThanOrEqual(m.h);
    }
  });

  test("a tall navigation scrolls inside the sidebar, not the page", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 500 });
    await signIn(page, "administrator", { "erpx.nav.groups": JSON.stringify(["workspace", "finance", "pentrix", "people-hr"]) });
    await page.goto("/");
    const r = await sidebar(page).evaluate((el) => { const s = el.querySelector("div.overflow-y-auto")!; return { client: s.clientHeight, scroll: s.scrollHeight, doc: document.documentElement.scrollHeight, h: innerHeight }; });
    expect(r.scroll).toBeGreaterThan(r.client);
    expect(r.doc).toBeLessThanOrEqual(r.h);
  });
});

test.describe("search", () => {
  test.use({ viewport: { width: 1366, height: 768 } });

  test("finds a page by name, shows its group, highlights the match, and Enter opens it", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    const box = sidebar(page).getByPlaceholder("Search modules...");
    await box.fill("vendor pay");
    const first = sidebar(page).getByRole("option").first();
    await expect(first).toContainText("Vendor Payments");
    await expect(first).toContainText("Finance");
    await expect(first.locator("mark").first()).toHaveText(/^Vendor/);
    await box.press("Enter");
    await expect(page).toHaveURL(/\/accounting\/payments/);
    await expect(box).toHaveValue("");
  });

  test("arrow keys move the highlight, Escape clears, and a miss says so", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    const box = sidebar(page).getByPlaceholder("Search modules...");
    await box.fill("leave");
    await expect(sidebar(page).getByRole("option")).toHaveCount(2); // Leave Types and Leave Applications (Workspace > Leave is for employees)
    await expect(sidebar(page).getByRole("option").first()).toHaveAttribute("aria-selected", "true");
    await box.press("ArrowDown");
    await expect(sidebar(page).getByRole("option").nth(1)).toHaveAttribute("aria-selected", "true");
    await box.press("Escape");
    await expect(box).toHaveValue("");
    await box.fill("zzzz-nothing");
    await expect(sidebar(page).getByText("No matching modules")).toBeVisible();
  });

  test("searches what is inside a page, and hidden pages", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    const box = sidebar(page).getByPlaceholder("Search modules...");
    await box.fill("booking settings");
    await expect(sidebar(page).getByRole("option")).toHaveCount(1);
    await box.press("Enter");
    await expect(page).toHaveURL(/\/pentrix-ops\/availability/);
  });

  test("Ctrl/Cmd+K focuses the sidebar's own box when pinned, and opens the palette when it is collapsed", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await page.keyboard.press(`${modKey}+k`);
    await expect(sidebar(page).getByPlaceholder("Search modules...")).toBeFocused();
    await page.getByRole("button", { name: "Collapse sidebar" }).click();
    await page.mouse.move(900, 400);
    await page.locator("main").click({ position: { x: 600, y: 300 } });
    await page.keyboard.press(`${modKey}+k`);
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByPlaceholder("Search modules...")).toBeFocused();
    await dialog.getByPlaceholder("Search modules...").fill("gst");
    await expect(dialog.getByRole("option").first()).toContainText("GST");
    await dialog.getByPlaceholder("Search modules...").press("Enter");
    await expect(page).toHaveURL(/\/accounting\/gst/);
    await expect(dialog).toHaveCount(0);
  });

  test("the rail's Search icon opens the same palette, and Escape closes it", async ({ page }) => {
    await signIn(page, "administrator", { "erpx.nav.mode": "collapsed" });
    await page.goto("/");
    await sidebar(page).getByRole("button", { name: "Search modules" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("Ctrl/Cmd+K does not hijack a rich-text editor that opts out", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await page.evaluate(() => {
      const d = document.createElement("div");
      d.contentEditable = "true";
      d.id = "ed";
      d.textContent = "x";
      document.querySelector("main")!.appendChild(d);
    });
    await page.locator("#ed").focus();
    await page.keyboard.press(`${modKey}+k`);
    await expect(sidebar(page).getByPlaceholder("Search modules...")).not.toBeFocused();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("works from inside an ordinary text field", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await page.evaluate(() => {
      const i = document.createElement("input");
      i.id = "plain";
      document.querySelector("main")!.appendChild(i);
    });
    await page.locator("#plain").focus();
    await page.keyboard.press(`${modKey}+k`);
    await expect(sidebar(page).getByPlaceholder("Search modules...")).toBeFocused();
  });

  for (const [who, query, expected] of [
    ["staff", "database backups", 0],
    ["staff", "roles", 0],
    ["administrator", "database backups", 0],
    ["administrator", "storage", 1],
    ["super_admin", "database backups", 1],
    ["super_admin", "invoices", 0],
    ["nobody", "finance", 0],
    ["pentrix_staff", "assigned bookings", 1],
    ["pentrix_staff", "invoices", 0],
  ] as const) {
    test(`search for "${query}" as ${who} finds ${expected}`, async ({ page }) => {
      await signIn(page, who);
      await page.goto("/");
      const box = sidebar(page).getByPlaceholder("Search modules...");
      await box.fill(query);
      await expect(sidebar(page).getByRole("option")).toHaveCount(expected);
    });
  }
});

test.describe("who sees what", () => {
  test.use({ viewport: { width: 1366, height: 768 } });
  const groupsOf = (page: Page) => sidebar(page).locator("button[id^='nav-group-']").allTextContents();

  test("an Administrator sees all 14 groups; Platform lists only Storage Manager", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    expect(await groupsOf(page)).toHaveLength(14);
    await group(page, "Platform").click();
    await expect(sidebar(page).getByRole("link", { name: "Storage Manager" })).toBeVisible();
    await expect(sidebar(page).getByRole("link", { name: "Database Backups" })).toHaveCount(0);
  });

  test("a Super Admin sees only the platform group (plus Dashboard and Calendar)", async ({ page }) => {
    await signIn(page, "super_admin");
    await page.goto("/");
    expect(await groupsOf(page)).toEqual(["Platform"]);
    await group(page, "Platform").click();
    for (const l of ["Organizations", "Storage Manager", "Database Backups", "System Health"]) await expect(sidebar(page).getByRole("link", { name: l })).toBeVisible();
  });

  test("Pentrix staff see only their assigned bookings", async ({ page }) => {
    await signIn(page, "pentrix_staff");
    await page.goto("/");
    expect(await groupsOf(page)).toEqual(["Workspace"]);
    await group(page, "Workspace").click();
    await expect(sidebar(page).getByRole("link")).toHaveCount(3); // Dashboard, Calendar, Assigned Bookings
  });

  test("a trainer sees the trainer workspace pages and nothing administrative", async ({ page }) => {
    await signIn(page, "trainer_only");
    await page.goto("/");
    expect(await groupsOf(page)).toEqual(["Workspace"]);
    await group(page, "Workspace").click();
    for (const l of ["Batches", "Live Classes", "Announcements", "Messages"]) await expect(sidebar(page).getByRole("link", { name: l })).toBeVisible();
    await expect(sidebar(page).getByRole("link", { name: "Attendance" })).toHaveCount(0);
  });

  test("a user with no permissions gets Dashboard and Calendar only", async ({ page }) => {
    await signIn(page, "nobody");
    await page.goto("/");
    expect(await groupsOf(page)).toEqual([]);
    await expect(sidebar(page).getByRole("link")).toHaveCount(2);
  });

  test("Workspace entries do not repeat 'My'", async ({ page }) => {
    await signIn(page, "administrator");
    await page.goto("/");
    await group(page, "Workspace").click();
    const items = await sidebar(page).locator("#nav-group-workspace a").allTextContents();
    expect(items).toEqual(["Batches", "Live Classes", "Announcements", "Messages", "Attendance", "Leave", "Payslips", "Expenses", "Schedule", "Approvals", "Assigned Bookings"].filter((l) => items.includes(l)));
    expect(items.some((l) => /^My /.test(l))).toBe(false);
  });
});

test.describe("route protection", () => {
  test.use({ viewport: { width: 1366, height: 768 } });
  const denied = (page: Page) => expect(page.getByText("You don't have access to this page")).toBeVisible();

  for (const [who, path] of [
    ["staff", "/administration/users"],
    ["staff", "/administration/backups"],
    ["staff", "/organizations"],
    ["administrator", "/administration/backups"],
    ["administrator", "/organizations"],
    ["pentrix_staff", "/accounting/invoices"],
    ["pentrix_staff", "/pentrix-ops/availability"], // hidden from the menu, still guarded
    ["pentrix_staff", "/pentrix-ops/payments/daily"],
    ["nobody", "/corporate/projects/abc-123"], // the gap this change closes
    ["nobody", "/courses/some-id"],
    ["trainer_only", "/employees"],
  ] as const) {
    test(`${who} is refused ${path}`, async ({ page }) => {
      await signIn(page, who);
      await page.goto(path);
      await denied(page);
    });
  }

  for (const [who, path] of [
    ["administrator", "/pentrix-ops/availability"],
    ["administrator", "/corporate/projects/abc-123"],
    ["super_admin", "/administration/backups"],
    ["nobody", "/"],
    ["nobody", "/events"],
  ] as const) {
    test(`${who} may open ${path}`, async ({ page }) => {
      await signIn(page, who);
      await page.goto(path);
      await expect(sidebar(page)).toBeVisible();
      await expect(page.getByText("You don't have access to this page")).toHaveCount(0);
    });
  }
});

test.describe("phone", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("has no sidebar, a menu button, and the page fills the width without sideways scroll", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await expect(slot(page)).toBeHidden();
    await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await mainLeft(page)).toBe(0);
  });

  test("the drawer has the search and the groups, opens a page by tap, and closes itself", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Open navigation" }).tap();
    const drawer = page.getByTestId("mobile-drawer");
    await expect(drawer).toBeVisible();
    expect((await drawer.boundingBox())!.width).toBeLessThanOrEqual(390 * 0.85 + 1);
    await expect(drawer.getByPlaceholder("Search modules...")).toBeVisible();
    await drawer.getByRole("button", { name: "Finance", exact: true }).tap();
    await drawer.getByRole("link", { name: "Invoices" }).tap();
    await expect(page).toHaveURL(/\/accounting\/invoices/);
    await expect(drawer).toHaveCount(0);
  });

  test("the drawer's search finds pages, and Escape closes the drawer", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Open navigation" }).tap();
    const drawer = page.getByTestId("mobile-drawer");
    await drawer.getByPlaceholder("Search modules...").fill("vendors");
    await expect(drawer.getByRole("option").first()).toContainText("Vendors");
    await page.keyboard.press("Escape"); // clears the text first
    await page.keyboard.press("Escape");
    await expect(drawer).toHaveCount(0);
  });

  test("the top bar's search button opens the palette", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Search modules" }).first().tap();
    await expect(page.getByRole("dialog")).toBeVisible();
  });

  test("a guarded page is still refused on a phone", async ({ page }) => {
    await signIn(page, "staff");
    await page.goto("/administration/users");
    await expect(page.getByText("You don't have access to this page")).toBeVisible();
  });
});

test.describe("in between", () => {
  for (const [w, h] of [[768, 1024], [1024, 768], [1180, 720], [683, 384]] as const) {
    test(`at ${w}x${h} nothing overflows and the navigation is reachable`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      await signIn(page);
      await page.goto("/");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (w >= 768) await expect(sidebar(page)).toBeVisible();
      else await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
    });
  }
});

test("every page the menu lists is reachable by its link (a sample from each group)", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await signIn(page);
  await page.goto("/");
  for (const [g, link, url] of [
    ["Communications", "Email Studio", /\/administration\/email-templates/],
    ["Internships", "Our Internships", /\/our-internships/],
    ["Students & Learning", "Question Bank", /\/examinations\/question-bank/],
    ["Pentrix", "Labs", /\/pentrix\/labs/],
    ["Finance", "Customer Receipts", /\/accounting\/receipts/],
    ["Administration", "Roles", /\/administration\/roles/],
  ] as const) {
    if ((await group(page, g).getAttribute("aria-expanded")) === "false") await group(page, g).click();
    await sidebar(page).locator(`#nav-group-${await group(page, g).evaluate((el) => el.id.replace(/^nav-group-|-button$/g, ""))}`).getByRole("link", { name: link, exact: true }).click();
    await expect(page).toHaveURL(url);
    await expect(page.getByText("You don't have access to this page")).toHaveCount(0);
  }
});
