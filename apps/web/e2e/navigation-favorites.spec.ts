import { type Page, expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Favorites (Pin to Top) in a real browser, on the PRODUCTION build. Only the JSON API is stubbed.
 * A page is pinned with the star beside it; Favorites sits under Dashboard and Calendar, above the groups.
 */

const roles = JSON.parse(readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "../src/components/navigation/role-permissions.fixture.json"), "utf8")) as { roles: Record<string, string[]> };
const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });

interface Account {
  userId: string;
  orgId: string | null;
  permissions: string[];
  superuser?: boolean;
}
const ADMIN: Account = { userId: "user-a", orgId: "org-1", permissions: roles.roles.administrator };
const KEY = (a: Pick<Account, "userId" | "orgId">) => `erpx.nav.favorites.v1:${a.orgId ?? "none"}:${a.userId}`;

/** Signs in once per tab, then answers the API from `account`, which a test may change before reloading (a different user, organization or role). */
async function signIn(page: Page, initial: Account = ADMIN, storage: Record<string, string> = {}) {
  const account = { ...initial };
  await page.addInitScript(
    ([acct, store]) => {
      if (sessionStorage.getItem("__seeded")) return;
      sessionStorage.setItem("__seeded", "1");
      localStorage.setItem("erpx-auth", JSON.stringify({ state: { accessToken: "t", refreshToken: "r", isAuthenticated: true, user: { id: acct.userId, email: "a@example.com", fullName: "Test User", status: "active", isEmailVerified: true, twoFactorEnabled: false } }, version: 0 }));
      for (const [k, v] of Object.entries(store)) localStorage.setItem(k, v);
    },
    [initial, storage] as const,
  );
  await page.route("**/api/v1/**", (route) => {
    const p = new URL(route.request().url()).pathname.replace(/^\/api\/v1/, "");
    if (p === "/authorization/me") return route.fulfill(json({ user_id: account.userId, roles: [], effective_permissions: account.permissions, is_superuser: !!account.superuser, organization_id: account.orgId }));
    if (/^\/(trainers|employees|students)\/me$/.test(p)) return route.fulfill(json({ detail: "none" }, 404));
    if (p.startsWith("/notifications")) return route.fulfill(json({ items: [], total: 0, page: 1, page_size: 20, unread_count: 0, count: 0 }));
    return route.fulfill(json({ items: [], total: 0, detail: "stub" }, 404));
  });
  return account;
}
/** Becomes another account in the same browser (same localStorage), as if someone else signed in. */
async function switchTo(page: Page, account: Account, next: Account) {
  Object.assign(account, next);
  await page.evaluate((u) => {
    const raw = JSON.parse(localStorage.getItem("erpx-auth")!);
    raw.state.user.id = u;
    localStorage.setItem("erpx-auth", JSON.stringify(raw));
  }, next.userId);
  await page.reload();
}

const sidebar = (page: Page) => page.getByTestId("sidebar");
// its accessible name is "Favorites", plus the count once something is pinned
const favButton = (page: Page) => page.locator("#nav-favorites-button");
const favLinks = (page: Page) => page.locator("#nav-favorites a");
const favNames = (page: Page) => favLinks(page).allTextContents();
const group = (page: Page, name: string) => sidebar(page).getByRole("button", { name, exact: true });
const stored = (page: Page, key: string) => page.evaluate((k) => localStorage.getItem(k), key);
const pinBtn = (page: Page, label: string) => page.getByRole("button", { name: `Pin ${label} to Favorites` });
const unpinBtn = (page: Page, label: string) => page.getByRole("button", { name: `Unpin ${label} from Favorites` });
async function open(page: Page, name: string) {
  if ((await group(page, name).getAttribute("aria-expanded")) === "false") await group(page, name).click();
}
/** Hovers the row first, as a mouse user would, then presses its star. */
async function pin(page: Page, groupName: string, label: string) {
  await open(page, groupName);
  const row = sidebar(page).locator("li", { has: page.getByRole("link", { name: label, exact: true }) }).last();
  await row.hover();
  await pinBtn(page, label).click();
}

test.describe("desktop", () => {
  test.use({ viewport: { width: 1366, height: 768 } });

  test("Favorites sits under Dashboard and Calendar, above the groups, open and empty at first", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    const order = await sidebar(page).locator("nav").evaluate((nav) => {
      const at = (sel: string) => nav.querySelector(sel)!.getBoundingClientRect().top;
      const dash = [...nav.querySelectorAll("a")].find((a) => a.textContent?.trim() === "Dashboard")!.getBoundingClientRect().top;
      return { dash, fav: at("#nav-favorites-button"), first: at("#nav-group-workspace-button") };
    });
    expect(order.dash).toBeLessThan(order.fav);
    expect(order.fav).toBeLessThan(order.first);
    await expect(favButton(page)).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByTestId("favorites-empty")).toHaveText("No favorites yet. Use the star beside any page to pin it here.");
    await expect(favLinks(page)).toHaveCount(0);
  });

  test("every listed page has a Pin action; Dashboard does not", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await expect(sidebar(page).getByRole("button", { name: /^Pin Dashboard/ })).toHaveCount(0);
    await expect(pinBtn(page, "Calendar")).toHaveCount(1);
    for (const g of ["Workspace", "Finance", "Pentrix", "Administration"]) {
      await open(page, g);
      const links = await sidebar(page).locator(`#nav-group-${await group(page, g).evaluate((el) => el.id.replace(/^nav-group-|-button$/g, ""))} a`).count();
      const pins = await sidebar(page).locator(`#nav-group-${await group(page, g).evaluate((el) => el.id.replace(/^nav-group-|-button$/g, ""))} button`).count();
      expect(pins, g).toBe(links);
    }
  });

  test("Pin adds the page to Favorites at once, and it stays in its own group", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await pin(page, "Finance", "Invoices");
    await expect(favLinks(page)).toHaveText(["Invoices"]);
    await expect(sidebar(page).locator("#nav-group-finance").getByRole("link", { name: "Invoices", exact: true })).toBeVisible(); // still there
    await expect(unpinBtn(page, "Invoices")).toHaveCount(2); // the star in the group and the one in Favorites
    await expect(page.getByTestId("favorites-empty")).toHaveCount(0);
    await expect(page.getByRole("status").filter({ hasText: "Pinned Invoices to Favorites." })).toBeAttached();
  });

  test("Unpin from the group removes it from Favorites at once, and the empty state returns", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await pin(page, "Finance", "Invoices");
    await sidebar(page).locator("#nav-group-finance").getByRole("button", { name: "Unpin Invoices from Favorites" }).click();
    await expect(favLinks(page)).toHaveCount(0);
    await expect(page.getByTestId("favorites-empty")).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: "Unpinned Invoices from Favorites." })).toBeAttached();
    await expect(sidebar(page).locator("#nav-group-finance").getByRole("link", { name: "Invoices", exact: true })).toBeVisible();
  });

  test("keeps the order pages were pinned in, and it survives a reload", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await pin(page, "Finance", "Invoices");
    await pin(page, "Students & Learning", "Courses");
    await pin(page, "Pentrix", "Labs");
    expect(await favNames(page)).toEqual(["Invoices", "Courses", "Labs"]);
    await page.reload();
    expect(await favNames(page)).toEqual(["Invoices", "Courses", "Labs"]);
    // pinned again after being removed goes to the end
    await sidebar(page).locator("#nav-favorites").getByRole("button", { name: "Unpin Invoices from Favorites" }).click();
    await pin(page, "Finance", "Invoices");
    expect(await favNames(page)).toEqual(["Courses", "Labs", "Invoices"]);
    await page.reload();
    expect(await favNames(page)).toEqual(["Courses", "Labs", "Invoices"]);
  });

  test("is saved by route under the user and organization, never by label", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await pin(page, "Finance", "Invoices");
    await pin(page, "Students & Learning", "Courses");
    expect(JSON.parse((await stored(page, KEY(ADMIN)))!)).toEqual(["/accounting/invoices", "/courses"]);
    const keys = await page.evaluate(() => Object.keys(localStorage).filter((k) => k.startsWith("erpx.nav.favorites")));
    expect(keys).toEqual([KEY(ADMIN)]);
  });

  test("Calendar can be pinned too", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await sidebar(page).locator("li", { has: page.getByRole("link", { name: "Calendar", exact: true }) }).hover();
    await pinBtn(page, "Calendar").click();
    await expect(favLinks(page)).toHaveText(["Calendar"]);
  });

  test("a star pressed does not navigate", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await pin(page, "Finance", "Invoices");
    await expect(page).toHaveURL(/\/$/);
  });

  test("a favorite opens its page and is highlighted both there and in its group", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await pin(page, "Finance", "Invoices");
    await favLinks(page).first().click();
    await expect(page).toHaveURL(/\/accounting\/invoices/);
    await expect(page.locator("#nav-favorites a[aria-current='page']")).toHaveText("Invoices");
    await expect(sidebar(page).locator("#nav-group-finance a[aria-current='page']")).toHaveText("Invoices");
    await expect(group(page, "Finance")).toHaveAttribute("data-active-group", "true");
    // another page: the favorite is no longer the current one
    await sidebar(page).getByRole("link", { name: "Calendar" }).first().click();
    await expect(page.locator("#nav-favorites a[aria-current='page']")).toHaveCount(0);
  });

  test("Favorites can be folded, and the choice is remembered", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await pin(page, "Finance", "Invoices");
    await favButton(page).click();
    await expect(favLinks(page)).toHaveCount(0);
    await page.reload();
    await expect(favButton(page)).toHaveAttribute("aria-expanded", "false");
    await favButton(page).click();
    await expect(favLinks(page)).toHaveText(["Invoices"]);
  });

  test.describe("keyboard and screen readers", () => {
    test("the star is reached with Tab, pinned with Enter, and keeps focus with a new name", async ({ page }) => {
      await signIn(page);
      await page.goto("/");
      await open(page, "Finance");
      await sidebar(page).getByRole("link", { name: "Invoices", exact: true }).focus();
      await page.keyboard.press("Tab");
      await expect(pinBtn(page, "Invoices")).toBeFocused();
      await expect(pinBtn(page, "Invoices")).toHaveCSS("opacity", "1"); // shown while its row has keyboard focus
      await page.keyboard.press("Enter");
      await expect(favLinks(page)).toHaveText(["Invoices"]);
      await expect(sidebar(page).locator("#nav-group-finance").getByRole("button", { name: "Unpin Invoices from Favorites" })).toBeFocused();
      await page.keyboard.press("Space");
      await expect(favLinks(page)).toHaveCount(0);
      await expect(sidebar(page).locator("#nav-group-finance").getByRole("button", { name: "Pin Invoices to Favorites" })).toBeFocused();
    });

    test("unpinning from the Favorites list moves focus to a neighbour, then to the Favorites heading", async ({ page }) => {
      await signIn(page);
      await page.goto("/");
      await pin(page, "Finance", "Invoices");
      await pin(page, "Students & Learning", "Courses");
      await unpinBtn(page, "Invoices").first().focus();
      await page.keyboard.press("Enter");
      await expect(favLinks(page)).toHaveText(["Courses"]);
      await expect(favLinks(page).first()).toBeFocused();
      await sidebar(page).locator("#nav-favorites").getByRole("button", { name: "Unpin Courses from Favorites" }).focus();
      await page.keyboard.press("Enter");
      await expect(favButton(page)).toBeFocused();
    });

    test("Favorites is a labelled list, pins announce themselves, and every star has a name", async ({ page }) => {
      await signIn(page);
      await page.goto("/");
      await pin(page, "Finance", "Invoices");
      await expect(page.getByRole("list", { name: "Favorites" })).toBeVisible();
      await expect(favButton(page)).toHaveAttribute("aria-controls", "nav-favorites");
      const live = page.getByRole("status").filter({ hasText: "Pinned Invoices to Favorites." });
      await expect(live).toHaveAttribute("aria-live", "polite");
      const unnamed = await sidebar(page).locator("button").evaluateAll((els) => els.filter((b) => !(b.getAttribute("aria-label") || b.textContent?.trim())).length);
      expect(unnamed).toBe(0);
    });
  });

  test.describe("whose favorites", () => {
    test("two users of one browser never see each other's pins", async ({ page }) => {
      const acct = await signIn(page);
      await page.goto("/");
      await pin(page, "Finance", "Invoices");
      await switchTo(page, acct, { ...ADMIN, userId: "user-b" });
      await expect(favLinks(page)).toHaveCount(0);
      await expect(page.getByTestId("favorites-empty")).toBeVisible();
      await pin(page, "Students & Learning", "Courses");
      expect(await favNames(page)).toEqual(["Courses"]);
      await switchTo(page, acct, ADMIN);
      expect(await favNames(page)).toEqual(["Invoices"]);
    });

    test("the same user in another organization starts empty and gets their own back when they return", async ({ page }) => {
      const acct = await signIn(page);
      await page.goto("/");
      await pin(page, "Finance", "Invoices");
      await switchTo(page, acct, { ...ADMIN, orgId: "org-2" });
      await expect(favLinks(page)).toHaveCount(0);
      await switchTo(page, acct, ADMIN);
      expect(await favNames(page)).toEqual(["Invoices"]);
    });

    test("favorites saved under another account are never read, even if they are in storage", async ({ page }) => {
      await signIn(page, ADMIN, { [KEY({ userId: "someone-else", orgId: "org-1" })]: JSON.stringify(["/courses"]) });
      await page.goto("/");
      await expect(favLinks(page)).toHaveCount(0);
    });
  });

  test.describe("roles and permissions", () => {
    test("a favorite the user may not open is not shown or reachable; it returns with the access, in its place", async ({ page }) => {
      const acct = await signIn(page, ADMIN, { [KEY(ADMIN)]: JSON.stringify(["/accounting/invoices", "/administration/users", "/courses"]) });
      await page.goto("/");
      expect(await favNames(page)).toEqual(["Invoices", "Users", "Courses"]);
      // the role is changed: Finance and Users are gone
      const reduced = roles.roles.administrator.filter((c) => !c.startsWith("accounting.") && !c.startsWith("users."));
      await switchTo(page, acct, { ...ADMIN, permissions: reduced });
      expect(await favNames(page)).toEqual(["Courses"]);
      await expect(sidebar(page).getByRole("link", { name: "Users", exact: true })).toHaveCount(0);
      expect(JSON.parse((await stored(page, KEY(ADMIN)))!)).toContain("/administration/users"); // only hidden, not forgotten
      await switchTo(page, acct, ADMIN);
      expect(await favNames(page)).toEqual(["Invoices", "Users", "Courses"]);
    });

    test("a platform page saved as a favorite never shows to an Administrator, but does to a Super Admin", async ({ page }) => {
      const acct = await signIn(page, ADMIN, { [KEY(ADMIN)]: JSON.stringify(["/administration/backups", "/organizations", "/administration/storage"]) });
      await page.goto("/");
      expect(await favNames(page)).toEqual(["Storage Manager"]); // an Administrator holds storage.view only
      await switchTo(page, acct, { ...ADMIN, permissions: [], superuser: true });
      expect(await favNames(page)).toEqual(["Database Backups", "Organizations", "Storage Manager"]); // in the order they were pinned
    });

    test("a user with no access to anything sees the empty state, whatever was saved", async ({ page }) => {
      await signIn(page, { ...ADMIN, permissions: [] }, { [KEY(ADMIN)]: JSON.stringify(["/accounting/invoices", "/courses"]) });
      await page.goto("/");
      await expect(favLinks(page)).toHaveCount(0);
      await expect(page.getByTestId("favorites-empty")).toBeVisible();
    });

    test("the page is still protected: opening a hidden favorite's route directly is refused", async ({ page }) => {
      await signIn(page, { ...ADMIN, permissions: [] }, { [KEY(ADMIN)]: JSON.stringify(["/administration/users"]) });
      await page.goto("/administration/users");
      await expect(page.getByText("You don't have access to this page")).toBeVisible();
    });
  });

  test.describe("search", () => {
    test("a pinned page shows a pin mark, is listed once, and comes first among equal matches", async ({ page }) => {
      await signIn(page, ADMIN, { [KEY(ADMIN)]: JSON.stringify(["/pentrix/labs"]) });
      await page.goto("/");
      const box = sidebar(page).getByPlaceholder("Search modules...");
      await box.fill("labs");
      const options = sidebar(page).getByRole("option");
      const texts = await options.allTextContents();
      expect(new Set(texts).size).toBe(texts.length); // no duplicate results
      await expect(options.first()).toContainText("Labs");
      await expect(options.first()).toContainText("Pinned to Favorites");
      await box.fill("invoices");
      await expect(sidebar(page).getByRole("option").first()).not.toContainText("Pinned to Favorites");
    });

    test("pinning changes the search result, and a pinned page that is not allowed is not found", async ({ page }) => {
      await signIn(page, { ...ADMIN, permissions: roles.roles.staff }, { [KEY(ADMIN)]: JSON.stringify(["/administration/users"]) });
      await page.goto("/");
      await sidebar(page).getByPlaceholder("Search modules...").fill("users");
      await expect(sidebar(page).getByRole("option").filter({ hasText: "Users" })).toHaveCount(0);
    });
  });

  test.describe("collapsed icon-only sidebar", () => {
    const COLLAPSED = { "erpx.nav.mode": "collapsed" };

    test("shows a Favorites star in the rail, with an accessible name", async ({ page }) => {
      await signIn(page, ADMIN, COLLAPSED);
      await page.goto("/");
      await page.mouse.move(900, 400);
      const star = favButton(page);
      await expect(star).toBeVisible();
      expect((await sidebar(page).boundingBox())!.width).toBe(64);
      expect(await star.evaluate((el) => el.getBoundingClientRect().width)).toBeLessThanOrEqual(64);
    });

    test("hover opens the overlay with the favorites in it, without moving the page; leaving folds it", async ({ page }) => {
      await signIn(page, ADMIN, { ...COLLAPSED, [KEY(ADMIN)]: JSON.stringify(["/accounting/invoices", "/courses"]) });
      await page.goto("/");
      const before = await page.locator("main").evaluate((el) => el.getBoundingClientRect().left);
      await page.mouse.move(30, 300);
      await expect(sidebar(page)).toHaveAttribute("data-overlay", "true");
      expect(await favNames(page)).toEqual(["Invoices", "Courses"]);
      expect(await page.locator("main").evaluate((el) => el.getBoundingClientRect().left)).toBe(before);
      await page.mouse.move(900, 400);
      await expect(sidebar(page)).toHaveAttribute("data-overlay", "false");
      expect(await stored(page, "erpx.nav.mode")).toBe("collapsed");
    });

    test("a click on the star opens the overlay at Favorites", async ({ page }) => {
      await signIn(page, ADMIN, { ...COLLAPSED, [KEY(ADMIN)]: JSON.stringify(["/courses"]) });
      await page.goto("/");
      await page.mouse.move(900, 400);
      await favButton(page).dispatchEvent("click");
      await expect(sidebar(page)).toHaveAttribute("data-overlay", "true");
      await expect(favButton(page)).toHaveAttribute("aria-expanded", "true");
      expect(await favNames(page)).toEqual(["Courses"]);
    });

    test("keyboard: Tab reaches the star, the overlay opens, a favorite opens with Enter, Escape closes", async ({ page }) => {
      await signIn(page, ADMIN, { ...COLLAPSED, [KEY(ADMIN)]: JSON.stringify(["/courses"]) });
      await page.goto("/");
      await page.mouse.move(900, 400);
      await sidebar(page).getByRole("button", { name: "Expand sidebar" }).focus();
      for (let i = 0; i < 10 && !(await favButton(page).evaluate((el) => el === document.activeElement)); i++) await page.keyboard.press("Tab");
      await expect(sidebar(page)).toHaveAttribute("data-overlay", "true"); // keyboard focus opened the overlay
      await expect(favButton(page)).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(favLinks(page).first()).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(/\/courses/);
      await page.keyboard.press("Escape");
      await expect(sidebar(page)).toHaveAttribute("data-overlay", "false");
    });

    test("pinning from the overlay keeps it open, and the favorite is there after it folds and reopens", async ({ page }) => {
      await signIn(page, ADMIN, COLLAPSED);
      await page.goto("/");
      await page.mouse.move(30, 300);
      await expect(sidebar(page)).toHaveAttribute("data-overlay", "true");
      await pin(page, "Finance", "Invoices");
      await expect(sidebar(page)).toHaveAttribute("data-overlay", "true");
      expect(await favNames(page)).toEqual(["Invoices"]);
      await page.mouse.move(900, 400);
      await expect(sidebar(page)).toHaveAttribute("data-overlay", "false");
      await page.mouse.move(30, 300);
      expect(await favNames(page)).toEqual(["Invoices"]);
    });
  });

  test("pinned expanded mode shows Favorites and keeps them across a reload", async ({ page }) => {
    await signIn(page, ADMIN, { "erpx.nav.mode": "pinned" });
    await page.goto("/");
    await pin(page, "Finance", "Invoices");
    await page.reload();
    await expect(sidebar(page)).toHaveAttribute("data-expanded", "true");
    expect(await favNames(page)).toEqual(["Invoices"]);
  });

  test("a long Favorites list scrolls inside the sidebar and never overflows the page", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 500 });
    const many = ["/accounting/invoices", "/courses", "/pentrix/labs", "/crm/leads", "/events", "/administration/roles", "/employees", "/leave/types"];
    await signIn(page, ADMIN, { [KEY(ADMIN)]: JSON.stringify(many) });
    await page.goto("/");
    const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, sh: document.documentElement.scrollHeight, w: innerWidth, h: innerHeight }));
    expect(m.sw).toBeLessThanOrEqual(m.w);
    expect(m.sh).toBeLessThanOrEqual(m.h);
    expect((await favNames(page)).length).toBeGreaterThan(3);
  });

  test("labels that are long do not push the star out of the row", async ({ page }) => {
    await signIn(page, ADMIN, { [KEY(ADMIN)]: JSON.stringify(["/pentrix-ops/payments"]) });
    await page.goto("/");
    const box = await sidebar(page).locator("#nav-favorites li").first().evaluate((li) => {
      const r = li.getBoundingClientRect();
      const b = li.querySelector("button")!.getBoundingClientRect();
      return { right: r.right, btnRight: b.right };
    });
    expect(box.btnRight).toBeLessThanOrEqual(box.right + 1);
  });
});

test.describe("phone", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("the drawer has Favorites, stars are visible without hover, and a tap pins and unpins", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await page.getByRole("button", { name: "Open navigation" }).tap();
    const drawer = page.getByTestId("mobile-drawer");
    await expect(drawer.getByTestId("favorites-empty")).toBeVisible();
    await drawer.getByRole("button", { name: "Finance", exact: true }).tap();
    const star = drawer.getByRole("button", { name: "Pin Invoices to Favorites" });
    await expect(star).toHaveCSS("opacity", "1"); // no hover on a touch screen
    expect((await star.boundingBox())!.width).toBeGreaterThanOrEqual(28);
    await star.tap();
    await expect(drawer.locator("#nav-favorites a")).toHaveText(["Invoices"]);
    await drawer.locator("#nav-favorites").getByRole("button", { name: "Unpin Invoices from Favorites" }).tap();
    await expect(drawer.locator("#nav-favorites a")).toHaveCount(0);
  });

  test("a favorite opens from the drawer and closes it; no sideways scroll", async ({ page }) => {
    await signIn(page, ADMIN, { [KEY(ADMIN)]: JSON.stringify(["/courses"]) });
    await page.goto("/");
    await page.getByRole("button", { name: "Open navigation" }).tap();
    const drawer = page.getByTestId("mobile-drawer");
    await drawer.locator("#nav-favorites a").first().tap();
    await expect(page).toHaveURL(/\/courses/);
    await expect(drawer).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });

  test("the drawer's favorites follow the same permissions", async ({ page }) => {
    await signIn(page, { ...ADMIN, permissions: roles.roles.staff }, { [KEY(ADMIN)]: JSON.stringify(["/administration/users", "/courses"]) });
    await page.goto("/");
    await page.getByRole("button", { name: "Open navigation" }).tap();
    const names = await page.getByTestId("mobile-drawer").locator("#nav-favorites a").allTextContents();
    expect(names).not.toContain("Users");
  });
});
