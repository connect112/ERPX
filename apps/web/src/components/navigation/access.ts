import { type GuardOnly, type NavGroup, type NavItem, allNavItems, guardOnly, navGroups, topItems } from "@/components/nav-config";

/** What the signed-in user is: the permissions their roles add up to, the superuser flag, and which self-service records they have. */
export interface NavContext {
  permissions: readonly string[];
  isSuperuser: boolean;
  isTrainer: boolean;
  isEmployee: boolean;
  isStudent: boolean;
}

type Gate = Pick<NavItem, "permission" | "superuserOnly" | "alsoSuperuser" | "ownership">;

/** The one rule for "may this user open this page", shared by the sidebar, the search and the route guard. */
export function isAllowed(item: Gate, ctx: NavContext): boolean {
  if (item.superuserOnly) return ctx.isSuperuser;
  if (item.ownership === "trainer") return ctx.isTrainer;
  if (item.ownership === "employee") return ctx.isEmployee;
  if (item.ownership === "student") return ctx.isStudent;
  if (item.permission) return ctx.permissions.includes(item.permission) || (item.alsoSuperuser === true && ctx.isSuperuser);
  return true;
}

export interface VisibleGroup {
  group: NavGroup;
  /** the entries listed in the menu (hidden ones are left out) */
  items: NavItem[];
}

/** Top-level entries and the groups with at least one listed entry the user may open. A group never shows without a permitted child. */
export function visibleNav(ctx: NavContext): { top: NavItem[]; groups: VisibleGroup[] } {
  return {
    top: topItems.filter((i) => isAllowed(i, ctx)),
    groups: navGroups
      .map((group) => ({ group, items: group.items.filter((i) => !i.hidden && isAllowed(i, ctx)) }))
      .filter((g) => g.items.length > 0),
  };
}

export interface SearchEntry {
  item: NavItem;
  /** the group's title, or null for a top-level entry */
  groupTitle: string | null;
}

/** Everything the user may open, hidden pages included, for the search. Nothing they may not open is ever returned. */
export function searchableEntries(ctx: NavContext): SearchEntry[] {
  const entries: SearchEntry[] = topItems.filter((i) => isAllowed(i, ctx)).map((item) => ({ item, groupTitle: null }));
  for (const group of navGroups) {
    for (const item of group.items) if (isAllowed(item, ctx)) entries.push({ item, groupTitle: group.title });
  }
  return entries;
}

interface Guard extends Gate {
  href: string;
}

const guards: Guard[] = [
  ...allNavItems.map((i): Guard => ({ href: i.href, permission: i.permission, superuserOnly: i.superuserOnly, alsoSuperuser: i.alsoSuperuser, ownership: i.ownership })),
  ...(guardOnly as GuardOnly[]).map((g): Guard => ({ href: g.href, permission: g.permission })),
]
  .filter((g) => g.permission || g.superuserOnly || g.ownership)
  // the longest href first, so a specific page is matched before the section it sits under
  .sort((a, b) => b.href.length - a.href.length);

/** The requirement for a path: the longest gated entry it equals or sits beneath. Undefined: open to any signed-in user. */
export function guardFor(pathname: string): Guard | undefined {
  return guards.find((g) => pathname === g.href || pathname.startsWith(`${g.href}/`));
}

/** The entry a path belongs to (the longest matching href, hidden ones included), for the active-page highlight. */
export function activeEntry(pathname: string): { item: NavItem; group: NavGroup | null } | null {
  let best: { item: NavItem; group: NavGroup | null } | null = null;
  const consider = (item: NavItem, group: NavGroup | null) => {
    const hit = item.href === "/" ? pathname === "/" : pathname === item.href || pathname.startsWith(`${item.href}/`);
    if (hit && (!best || item.href.length > best.item.href.length)) best = { item, group };
  };
  topItems.forEach((i) => consider(i, null));
  navGroups.forEach((g) => g.items.forEach((i) => consider(i, g)));
  return best;
}
