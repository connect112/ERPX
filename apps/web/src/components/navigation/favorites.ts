import { type NavGroup, type NavItem, navGroups, topItems } from "@/components/nav-config";
import { type NavContext, isAllowed } from "@/components/navigation/access";

/**
 * Favorites: pages a user pinned to the top of the sidebar.
 *
 * - A favorite is stored as the page's ROUTE (its href), never its label, so renaming a module cannot break a saved favorite.
 * - Favorites live in this browser only (no server storage), under a key made from the organization AND the user, so two accounts
 *   sharing a browser never see each other's pins.
 * - What is stored is only "what the user pinned, in the order they pinned it". Whether a pin is SHOWN is decided every time from the
 *   user's current permissions (resolveFavorites), so losing access hides a favorite and regaining it brings it back.
 */

/** The id of the Favorites section among the sidebar's collapsible sections (no real group may use it). */
export const FAVORITES_GROUP_ID = "favorites";
const KEY_PREFIX = "erpx.nav.favorites.v1";

export interface FavoritesScope {
  userId: string;
  /** null when the account has no organization (a platform superuser) or the server did not say */
  organizationId: string | null;
}

export const favoritesKey = (scope: FavoritesScope) => `${KEY_PREFIX}:${encodeURIComponent(scope.organizationId ?? "none")}:${encodeURIComponent(scope.userId)}`;

export interface Pinnable {
  item: NavItem;
  /** the group the page is listed under, or null for a top-level page */
  group: NavGroup | null;
}

/** Every page that can be pinned, by route: all pages listed in the menu except Dashboard (which is always at the top anyway). */
const pinnable = new Map<string, Pinnable>();
for (const item of topItems) if (item.href !== "/") pinnable.set(item.href, { item, group: null });
for (const group of navGroups) for (const item of group.items) if (!item.hidden) pinnable.set(item.href, { item, group });

/** The stable identifier a favorite is saved under. */
export const routeId = (item: Pick<NavItem, "href">) => item.href;
export const isPinnable = (id: string) => pinnable.has(id);

/** Reads the saved favorites: route ids in pin order, without duplicates, and without routes that no longer exist. Never throws. */
export function readFavorites(scope: FavoritesScope): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(favoritesKey(scope)) ?? "[]") as unknown;
    if (!Array.isArray(raw)) return [];
    return [...new Set(raw.filter((v): v is string => typeof v === "string" && pinnable.has(v)))];
  } catch {
    return [];
  }
}

export function writeFavorites(scope: FavoritesScope, ids: readonly string[]) {
  try {
    localStorage.setItem(favoritesKey(scope), JSON.stringify(ids));
  } catch {
    /* a blocked store only means the pins are not remembered */
  }
}

/** Pins a page at the end of the list, or unpins it. */
export function togglePin(ids: readonly string[], id: string): string[] {
  if (ids.includes(id)) return ids.filter((x) => x !== id);
  return pinnable.has(id) ? [...ids, id] : [...ids];
}

/** The favorites to show: in pin order, only pages this user may open right now. */
export function resolveFavorites(ids: readonly string[], ctx: NavContext): Pinnable[] {
  const shown: Pinnable[] = [];
  for (const id of ids) {
    const p = pinnable.get(id);
    if (p && isAllowed(p.item, ctx) && !shown.some((s) => s.item.href === id)) shown.push(p);
  }
  return shown;
}
