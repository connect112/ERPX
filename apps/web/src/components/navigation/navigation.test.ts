import fs from "node:fs";
import { describe, expect, it } from "vitest";

import { allNavItems, guardOnly, navGroups, topItems } from "@/components/nav-config";
import { type NavContext, activeEntry, guardFor, isAllowed, searchableEntries, visibleNav } from "@/components/navigation/access";
import legacy from "@/components/navigation/legacy-nav.fixture.json";
import roles from "@/components/navigation/role-permissions.fixture.json";
import { highlight, searchNav } from "@/components/navigation/search";

const roleCtx = (slug: keyof typeof roles.roles, over: Partial<NavContext> = {}): NavContext => ({ permissions: roles.roles[slug], isSuperuser: false, isTrainer: false, isEmployee: false, isStudent: false, ...over });
const SUPER: NavContext = { permissions: [], isSuperuser: true, isTrainer: false, isEmployee: false, isStudent: false };
const NOBODY: NavContext = { permissions: [], isSuperuser: false, isTrainer: false, isEmployee: false, isStudent: false };
const labelsOf = (ctx: NavContext) => visibleNav(ctx).groups.map((g) => g.group.title);

describe("the navigation hierarchy", () => {
  it("is the agreed structure, group by group", () => {
    expect(topItems.map((i) => i.label)).toEqual(["Dashboard", "Calendar"]);
    const shown = Object.fromEntries(navGroups.map((g) => [g.title, g.items.filter((i) => !i.hidden).map((i) => i.label)]));
    expect(shown).toEqual({
      Workspace: ["Batches", "Live Classes", "Announcements", "Messages", "Attendance", "Leave", "Payslips", "Expenses", "Schedule", "Approvals", "Assigned Bookings"],
      Internships: ["Our Internships", "Internship Postings", "Active Internships"],
      "Students & Learning": ["Admissions", "Students", "Courses", "Batches", "Classrooms", "Question Bank", "Badges"],
      "Events & Institutions": ["Institutions", "Workshops", "Workshop Exams", "Hackathons"],
      Pentrix: ["Overview", "Registrations", "Assessments", "Bookings", "Payments", "Marketing", "Labs", "Challenges", "Leaderboard", "Achievements"],
      "Marketing & Sales": ["Leads", "Campaigns", "Landing Pages", "Coupons", "Referrals", "Referral Programs", "Marketing Overview", "Social Media", "Media Gallery"],
      "Careers & Alumni": ["Placement Companies", "Job Postings", "Job Feed", "Alumni Profiles", "Alumni Events", "Job Referrals"],
      Communications: ["Announcements", "Student-Trainer Messages", "Broadcast Notifications", "Email Studio", "Manual Communications"],
      "People & HR": ["Employees", "Trainers", "Departments & Designations", "Attendance", "Leave Types", "Leave Applications", "Expense Claims", "Salary Components", "Payroll Runs"],
      Finance: ["Invoices", "Customer Receipts", "Expenses", "Vendor Payments", "Customers", "Vendors", "Bank Accounts", "Journals", "Chart of Accounts", "GST", "TDS", "Financial Reports"],
      "Operations & Assets": ["Purchase Orders", "Inventory Items", "Item Categories & Warehouses", "Fixed Assets", "Asset Categories", "Depreciation Runs"],
      Corporate: ["Clients", "Corporate Reports"],
      Administration: ["Users", "Roles", "Audit Logs", "Approval Requests", "Approval Workflows", "Integrations"],
      Platform: ["Organizations", "Storage Manager", "Database Backups", "System Health"],
    });
  });

  it("keeps two levels, no duplicate routes, and the Workspace labels free of 'My'", () => {
    const hrefs = allNavItems.map((i) => i.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
    expect(navGroups.find((g) => g.id === "workspace")!.items.every((i) => !/^My /.test(i.label))).toBe(true);
    expect(navGroups.length).toBe(14);
  });

  it("has two pages that are routable and searchable but not listed: they are reached from their parent page", () => {
    expect(allNavItems.filter((i) => i.hidden).map((i) => i.href)).toEqual(["/pentrix-ops/payments/daily", "/pentrix-ops/availability"]);
  });
});

describe("every entry of the old sidebar is still there, with the same gate", () => {
  const byHref = new Map(allNavItems.map((i) => [i.href, i]));
  it("accounts for all 99", () => {
    expect(legacy.entries.length).toBe(99);
    const missing = legacy.entries.filter((e) => !byHref.has(e.href)).map((e) => e.href);
    expect(missing).toEqual(["/administration/bulk-downloads"]); // moved to the account menu: it lists only the signed-in user's own downloads
  });

  it.each(legacy.entries.filter((e) => e.href !== "/administration/bulk-downloads"))("$label ($href) keeps its requirement", (old) => {
    const now = byHref.get(old.href)!;
    expect({ permission: now.permission, superuserOnly: now.superuserOnly, alsoSuperuser: now.alsoSuperuser, ownership: now.ownership }).toEqual({
      permission: (old as { permission?: string }).permission,
      superuserOnly: (old as { superuserOnly?: boolean }).superuserOnly,
      alsoSuperuser: (old as { alsoSuperuser?: boolean }).alsoSuperuser,
      ownership: (old as { ownership?: string }).ownership,
    });
  });

  it("opens exactly the pages it used to for every system role (same gate, same answer)", () => {
    const ctxs = [roleCtx("administrator"), roleCtx("staff"), roleCtx("pentrix_staff"), roleCtx("student"), roleCtx("hackathon_participant"), SUPER, NOBODY, roleCtx("staff", { isTrainer: true, isEmployee: true, isStudent: true })];
    for (const ctx of ctxs) {
      for (const old of legacy.entries) {
        if (!byHref.has(old.href)) continue;
        const before = isAllowed(old as never, ctx);
        expect(isAllowed(byHref.get(old.href)!, ctx), `${old.label} for ${JSON.stringify([ctx.isSuperuser, ctx.permissions.length])}`).toBe(before);
      }
    }
  });
});

describe("who sees which groups", () => {
  it("shows an Administrator every group and every listed page, and a plain Staff member only what their permissions allow", () => {
    const admin = visibleNav(roleCtx("administrator", { isTrainer: true, isEmployee: true, isStudent: true }));
    expect(admin.groups.length).toBe(14);
    // Platform holds one page an Administrator may open (Storage Manager, permission-gated); the rest need a superuser
    expect(admin.groups.find((g) => g.group.title === "Platform")!.items.map((i) => i.label)).toEqual(["Storage Manager"]);
    const staff = labelsOf(roleCtx("staff"));
    expect(staff).toContain("Finance");
    expect(staff).not.toContain("Platform");
    const adminPages = visibleNav(roleCtx("staff")).groups.find((g) => g.group.title === "Administration")?.items.map((i) => i.label) ?? [];
    for (const forbidden of ["Users", "Roles", "Audit Logs", "Integrations"]) expect(adminPages).not.toContain(forbidden);
  });

  it("gives a Super Admin the platform pages and nothing permission-gated, plus the open top-level pages", () => {
    const v = visibleNav(SUPER);
    expect(v.top.map((i) => i.label)).toEqual(["Dashboard", "Calendar"]);
    expect(v.groups.map((g) => [g.group.title, g.items.map((i) => i.label)])).toEqual([["Platform", ["Organizations", "Storage Manager", "Database Backups", "System Health"]]]);
  });

  it("shows nothing but the open pages to someone with no permissions, and Workspace only for their own records", () => {
    expect(visibleNav(NOBODY).groups).toEqual([]);
    const trainer = visibleNav({ ...NOBODY, isTrainer: true });
    expect(trainer.groups.map((g) => [g.group.title, g.items.map((i) => i.label)])).toEqual([["Workspace", ["Batches", "Live Classes", "Announcements", "Messages"]]]);
    const employee = visibleNav({ ...NOBODY, isEmployee: true });
    expect(employee.groups[0].items.map((i) => i.label)).toEqual(["Attendance", "Leave", "Payslips", "Expenses"]);
  });

  it("shows a Pentrix staff member only their assigned bookings", () => {
    const v = visibleNav(roleCtx("pentrix_staff"));
    expect(v.groups.map((g) => [g.group.title, g.items.map((i) => i.label)])).toEqual([["Workspace", ["Assigned Bookings"]]]);
  });

  it("never shows a group without a page the user may open, whatever mix of roles and custom permissions they hold", () => {
    const all = roles.roles.administrator;
    const pick = (n: number, seed: number) => all.filter((_, i) => (i * 2654435761 + seed) % 7 < n);
    for (let seed = 0; seed < 40; seed++) {
      const ctx: NavContext = { permissions: pick(seed % 5, seed), isSuperuser: seed % 11 === 0, isTrainer: seed % 3 === 0, isEmployee: seed % 4 === 0, isStudent: seed % 5 === 0 };
      for (const { group, items } of visibleNav(ctx).groups) {
        expect(items.length, group.title).toBeGreaterThan(0);
        expect(items.every((i) => isAllowed(i, ctx) && !i.hidden)).toBe(true);
      }
    }
  });

  it("adds up the permissions of several roles", () => {
    const both = { ...NOBODY, permissions: [...roles.roles.pentrix_staff, "accounting.invoices.view"] };
    expect(labelsOf(both)).toEqual(["Workspace", "Finance"]);
  });
});

describe("route protection", () => {
  it.each(allNavItems.filter((i) => i.permission || i.superuserOnly || i.ownership))("guards $href and everything beneath it with its own requirement", (item) => {
    for (const path of [item.href, `${item.href}/some-id`]) {
      const g = guardFor(path);
      expect(g, path).toBeDefined();
      expect({ permission: g!.permission, superuserOnly: g!.superuserOnly, ownership: g!.ownership }).toEqual({ permission: item.permission, superuserOnly: item.superuserOnly, ownership: item.ownership });
    }
  });

  it("protects hidden pages like any other", () => {
    expect(isAllowed(guardFor("/pentrix-ops/availability")!, roleCtx("pentrix_staff"))).toBe(false);
    expect(isAllowed(guardFor("/pentrix-ops/availability")!, roleCtx("administrator"))).toBe(true);
    expect(isAllowed(guardFor("/pentrix-ops/payments/daily")!, roleCtx("administrator"))).toBe(true);
  });

  it("closes the corporate project page gap", () => {
    expect(guardOnly).toContainEqual({ href: "/corporate/projects", permission: "corporate.projects.view" });
    const g = guardFor("/corporate/projects/abc-123");
    expect(g?.permission).toBe("corporate.projects.view");
    expect(isAllowed(g!, NOBODY)).toBe(false);
    expect(isAllowed(g!, roleCtx("administrator"))).toBe(true);
  });

  it("leaves the open pages open", () => {
    for (const path of ["/", "/events", "/account-settings"]) expect(guardFor(path)).toBeUndefined();
  });

  it("covers every page route the router declares (or says why not)", () => {
    const source = fs.readFileSync("src/router/index.tsx", "utf8");
    const open = new Set(["", "/", "events", "account-settings", "administration/bulk-downloads"]); // the last lists only the signed-in user's own downloads
    // children of the Email Studio route are relative paths under administration/email-templates, which is guarded
    const studioChildren = new Set(["create", "brands", "components", "signatures", "history"]);
    const paths = [...source.matchAll(/\{\s*path:\s*"([^"]*)"/g)].map((m) => m[1]).filter((p) => !p.startsWith("/"));
    const unguarded = paths.filter((p) => !open.has(p) && !studioChildren.has(p) && !guardFor(`/${p}`));
    expect(unguarded).toEqual([]);
  });
});

describe("the active page", () => {
  it("finds the entry and group for a page, detail pages and hidden pages included", () => {
    expect(activeEntry("/courses/abc")?.item.label).toBe("Courses");
    expect(activeEntry("/courses/abc")?.group?.title).toBe("Students & Learning");
    expect(activeEntry("/courses/categories")?.item.href).toBe("/courses");
    expect(activeEntry("/pentrix-ops/payments/daily")?.item.href).toBe("/pentrix-ops/payments/daily"); // the more specific entry wins
    expect(activeEntry("/pentrix-ops/payments/daily")?.group?.title).toBe("Pentrix");
    expect(activeEntry("/")?.group).toBeNull();
    expect(activeEntry("/events")?.item.label).toBe("Calendar");
    expect(activeEntry("/account-settings")).toBeNull();
  });
});

describe("navigation search", () => {
  const admin = searchableEntries(roleCtx("administrator", { isTrainer: true, isEmployee: true }));
  const top = (q: string, ctx = admin) => searchNav(ctx, q).map((r) => `${r.entry.groupTitle ? r.entry.groupTitle + " > " : ""}${r.entry.item.label}`);

  it("finds a page by its name, with its group shown, best match first", () => {
    expect(top("vendor pay")[0]).toBe("Finance > Vendor Payments");
    expect(top("our int")[0]).toBe("Internships > Our Internships");
    expect(top("gst")[0]).toBe("Finance > GST");
  });

  it("finds a page by what is inside it", () => {
    expect(top("offer letters")).toContain("Internships > Our Internships");
    expect(top("learning paths")).toContain("Students & Learning > Courses");
    expect(top("cashfree")).toContain("Administration > Integrations");
  });

  it("finds a whole group by its name, and hidden pages", () => {
    const finance = top("finance");
    expect(finance.length).toBeGreaterThan(8);
    expect(finance.every((l) => l.startsWith("Finance > "))).toBe(true);
    expect(top("booking settings")).toEqual(["Pentrix > Booking Settings"]);
    expect(top("daily payment")[0]).toBe("Pentrix > Daily Payment Summary");
  });

  it("says nothing for a query that matches nothing, and for an empty one", () => {
    expect(top("zzzz-nothing")).toEqual([]);
    expect(top("   ")).toEqual([]);
  });

  it("is not thrown by case, accents or extra spaces", () => {
    expect(top("  VENDOR   payments ")[0]).toBe("Finance > Vendor Payments");
    expect(top("Émployees")[0]).toBe("People & HR > Employees");
  });

  it("never returns a page the user may not open", () => {
    const allowed = (ctx: NavContext) => new Set(allNavItems.filter((i) => isAllowed(i, ctx)).map((i) => i.href));
    for (const ctx of [roleCtx("staff"), roleCtx("pentrix_staff"), roleCtx("student"), SUPER, NOBODY, roleCtx("administrator")]) {
      const entries = searchableEntries(ctx);
      const ok = allowed(ctx);
      for (const q of ["a", "e", "pay", "finance", "platform", "backups", "users", "organizations", "settings", "email", "internship"]) {
        for (const r of searchNav(entries, q, 100)) expect(ok.has(r.entry.item.href), `${q} -> ${r.entry.item.href}`).toBe(true);
      }
    }
    expect(searchNav(searchableEntries(roleCtx("administrator")), "database backups")).toEqual([]); // platform-only, even for an Administrator
    expect(searchNav(searchableEntries(SUPER), "database backups").length).toBe(1);
    expect(searchNav(searchableEntries(NOBODY), "finance")).toEqual([]);
  });

  it("highlights the matching part of a label", () => {
    const r = searchNav(admin, "vendor")[0];
    expect(highlight(r.entry.item.label, r.ranges)).toEqual([{ text: "Vendor", match: true }, { text: " Payments", match: false }]);
    expect(highlight("Courses", [])).toEqual([{ text: "Courses", match: false }]);
  });
});
