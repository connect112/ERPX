// @vitest-environment happy-dom
import { beforeEach, describe, expect, it, vi } from "vitest";

import { allNavItems, navGroups, topItems } from "@/components/nav-config";
import type { NavContext } from "@/components/navigation/access";
import { FAVORITES_GROUP_ID, favoritesKey, isPinnable, readFavorites, resolveFavorites, routeId, togglePin, writeFavorites } from "@/components/navigation/favorites";
import roles from "@/components/navigation/role-permissions.fixture.json";
import { searchNav } from "@/components/navigation/search";
import { searchableEntries } from "@/components/navigation/access";

const ctxOf = (permissions: string[], over: Partial<NavContext> = {}): NavContext => ({ permissions, isSuperuser: false, isTrainer: false, isEmployee: false, isStudent: false, ...over });
const ADMIN = ctxOf(roles.roles.administrator);
const A = { userId: "user-a", organizationId: "org-1" };

beforeEach(() => localStorage.clear());

describe("what can be pinned", () => {
  it("is every listed page except Dashboard, identified by its route", () => {
    expect(isPinnable("/")).toBe(false); // Dashboard is always at the top
    expect(isPinnable("/events")).toBe(true); // Calendar
    expect(isPinnable("/accounting/invoices")).toBe(true);
    expect(isPinnable("/pentrix-ops/availability")).toBe(false); // not listed in the menu
    expect(isPinnable("/nowhere")).toBe(false);
    const listed = [...topItems.filter((i) => i.href !== "/"), ...navGroups.flatMap((g) => g.items.filter((i) => !i.hidden))];
    for (const item of listed) expect(isPinnable(routeId(item))).toBe(true);
  });

  it("never collides with a real group id", () => {
    expect(navGroups.map((g) => g.id)).not.toContain(FAVORITES_GROUP_ID);
  });
});

describe("saving", () => {
  it("keeps the order pages were pinned in, and unpinning removes only that page", () => {
    let ids: string[] = [];
    for (const id of ["/accounting/invoices", "/courses", "/events"]) ids = togglePin(ids, id);
    expect(ids).toEqual(["/accounting/invoices", "/courses", "/events"]);
    ids = togglePin(ids, "/courses");
    expect(ids).toEqual(["/accounting/invoices", "/events"]);
    ids = togglePin(ids, "/courses"); // pinned again: goes to the end
    expect(ids).toEqual(["/accounting/invoices", "/events", "/courses"]);
  });

  it("does not pin something that is not a page of the menu", () => {
    expect(togglePin([], "/")).toEqual([]);
    expect(togglePin([], "/made-up")).toEqual([]);
  });

  it("round-trips through the browser store, in order", () => {
    writeFavorites(A, ["/courses", "/accounting/invoices"]);
    expect(readFavorites(A)).toEqual(["/courses", "/accounting/invoices"]);
  });

  it("is stored by route, not label, so the label can change without losing the favorite", () => {
    writeFavorites(A, ["/accounting/invoices"]);
    expect(localStorage.getItem(favoritesKey(A))).toBe('["/accounting/invoices"]');
    const original = allNavItems.find((i) => i.href === "/accounting/invoices")!;
    const renamed = { ...original, label: "Sales Invoices" };
    expect(routeId(renamed)).toBe(routeId(original));
  });

  it("survives garbage, duplicates and routes that no longer exist", () => {
    localStorage.setItem(favoritesKey(A), "{not json");
    expect(readFavorites(A)).toEqual([]);
    localStorage.setItem(favoritesKey(A), JSON.stringify({ a: 1 }));
    expect(readFavorites(A)).toEqual([]);
    localStorage.setItem(favoritesKey(A), JSON.stringify(["/courses", 7, null, "/courses", "/gone/forever", "/events"]));
    expect(readFavorites(A)).toEqual(["/courses", "/events"]);
  });

  it("is not an error when the browser blocks storage", () => {
    const blocked = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
    vi.stubGlobal("localStorage", blocked);
    try {
      expect(readFavorites(A)).toEqual([]);
      expect(() => writeFavorites(A, ["/courses"])).not.toThrow();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("whose favorites they are", () => {
  it("keeps two users of the same browser apart", () => {
    writeFavorites({ userId: "user-a", organizationId: "org-1" }, ["/courses"]);
    writeFavorites({ userId: "user-b", organizationId: "org-1" }, ["/events"]);
    expect(readFavorites({ userId: "user-a", organizationId: "org-1" })).toEqual(["/courses"]);
    expect(readFavorites({ userId: "user-b", organizationId: "org-1" })).toEqual(["/events"]);
    expect(readFavorites({ userId: "user-c", organizationId: "org-1" })).toEqual([]);
  });

  it("keeps the same user in two organizations apart", () => {
    writeFavorites({ userId: "user-a", organizationId: "org-1" }, ["/courses"]);
    expect(readFavorites({ userId: "user-a", organizationId: "org-2" })).toEqual([]);
    expect(readFavorites({ userId: "user-a", organizationId: null })).toEqual([]);
  });

  it("cannot be confused by ids that contain the separator", () => {
    expect(favoritesKey({ userId: "b:c", organizationId: "a" })).not.toBe(favoritesKey({ userId: "c", organizationId: "a:b" }));
  });
});

describe("what is shown", () => {
  const pins = ["/accounting/invoices", "/courses", "/administration/users", "/events", "/administration/backups"];

  it("shows pins in pin order, only the pages the user may open", () => {
    const staff = ctxOf(roles.roles.staff);
    const shown = resolveFavorites(pins, staff).map((p) => p.item.href);
    expect(shown).toEqual(pins.filter((p) => !["/administration/users", "/administration/backups"].includes(p)).filter((p) => resolveFavorites([p], staff).length));
    expect(shown).not.toContain("/administration/users");
    expect(shown).not.toContain("/administration/backups");
    expect(shown[0]).toBe("/accounting/invoices");
  });

  it("hides a favorite when access is lost and brings it back when it returns, without re-pinning", () => {
    const ids = ["/accounting/invoices", "/courses"];
    expect(resolveFavorites(ids, ADMIN).map((p) => p.item.href)).toEqual(ids);
    const withoutFinance = ctxOf(roles.roles.administrator.filter((p) => !p.startsWith("accounting.")));
    expect(resolveFavorites(ids, withoutFinance).map((p) => p.item.href)).toEqual(["/courses"]);
    expect(resolveFavorites(ids, ADMIN).map((p) => p.item.href)).toEqual(ids);
  });

  it("never shows a platform page to someone who is not a superuser, or an ownership page to someone without the record", () => {
    expect(resolveFavorites(["/administration/backups", "/organizations"], ADMIN)).toEqual([]);
    expect(resolveFavorites(["/administration/backups"], ctxOf([], { isSuperuser: true })).length).toBe(1);
    expect(resolveFavorites(["/my/batches"], ctxOf([])).length).toBe(0);
    expect(resolveFavorites(["/my/batches"], ctxOf([], { isTrainer: true })).length).toBe(1);
  });

  it("shows nothing for a user with nothing pinned", () => {
    expect(resolveFavorites([], ADMIN)).toEqual([]);
  });

  it("lists a page once even if the saved list repeats it, and tells the group of each", () => {
    const shown = resolveFavorites(["/courses", "/courses", "/events"], ADMIN);
    expect(shown.map((p) => p.item.href)).toEqual(["/courses", "/events"]);
    expect(shown[0].group?.title).toBe("Students & Learning");
    expect(shown[1].group).toBeNull();
  });

  it("every permission-fixture role gets only pages it may open", () => {
    const everything = [...topItems.filter((i) => i.href !== "/"), ...navGroups.flatMap((g) => g.items.filter((i) => !i.hidden))].map((i) => i.href);
    for (const slug of Object.keys(roles.roles) as (keyof typeof roles.roles)[]) {
      const ctx = ctxOf(roles.roles[slug]);
      const allowedHrefs = new Set(searchableEntries(ctx).map((e) => e.item.href));
      for (const p of resolveFavorites(everything, ctx)) expect(allowedHrefs.has(p.item.href), `${slug} ${p.item.href}`).toBe(true);
    }
  });
});

describe("search and favorites", () => {
  const entries = searchableEntries(ADMIN);
  it("lists a pinned page once, and puts it first among equally good matches", () => {
    const plain = searchNav(entries, "attendance").map((r) => r.entry.item.href);
    expect(new Set(plain).size).toBe(plain.length);
    const last = plain[plain.length - 1];
    const withPin = searchNav(entries, "attendance", 12, new Set([last])).map((r) => r.entry.item.href);
    expect(withPin[0]).toBe(last);
    expect(withPin.length).toBe(plain.length);
    expect(new Set(withPin).size).toBe(withPin.length);
  });

  it("a pin never lifts a worse match above a better one", () => {
    const exact = searchNav(entries, "gst")[0].entry.item.href;
    const results = searchNav(entries, "gst", 12, new Set(["/courses"])).map((r) => r.entry.item.href);
    expect(results[0]).toBe(exact);
  });
});
