import { ChevronDown, ChevronRight, Star } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";

import type { NavItem } from "@/components/nav-config";
import { type NavContext, activeEntry, visibleNav } from "@/components/navigation/access";
import { FAVORITES_GROUP_ID, isPinnable, resolveFavorites } from "@/components/navigation/favorites";
import { useNavFavorites } from "@/components/navigation/favorites-state";
import { useNavLayout } from "@/components/navigation/nav-state";
import { cn } from "@/lib/utils";

/** The star at the end of a row that pins the page to Favorites (or unpins it). A sibling of the link, never inside it. */
function PinButton({ item, pinned, onToggle, onDark, always }: { item: NavItem; pinned: boolean; onToggle: () => void; onDark: boolean; always?: boolean }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={pinned ? `Unpin ${item.label} from Favorites` : `Pin ${item.label} to Favorites`}
      title={pinned ? "Unpin from Favorites" : "Pin to Favorites"}
      className={cn(
        "absolute right-1 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md transition-opacity focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        onDark ? "text-primary-foreground hover:bg-primary-foreground/20" : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        // shown on hover or keyboard focus of the row, always when pinned, and always on a touch screen (which has no hover)
        pinned || always ? "opacity-100" : "opacity-0 group-focus-within:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100"
      )}
    >
      <Star className={cn("h-4 w-4", pinned && (onDark ? "fill-current" : "fill-current text-amber-500"))} aria-hidden />
    </button>
  );
}

/**
 * The navigation list, used by the desktop sidebar (expanded and icon-only) and by the mobile drawer.
 *
 * The same elements stay mounted whether labels are showing or not: when the sidebar is collapsed the labels are only visually hidden
 * (still read by screen readers) and the group's own icon stands for the group. That keeps keyboard focus where it is when the sidebar
 * opens and closes around it. `expanded` false therefore means "icon rail", never "hidden".
 *
 * Favorites is one more such section, between Dashboard/Calendar and the groups. Pinning never moves a page: it stays in its own group.
 */
export function NavTree({ ctx, expanded, onNavigate, onGroupIconClick }: { ctx: NavContext; expanded: boolean; onNavigate?: () => void; onGroupIconClick?: (groupId: string) => void }) {
  const { pathname } = useLocation();
  const { openGroups, toggleGroup, openGroup } = useNavLayout();
  const { ids, isPinned, toggle, announcement, ready: favoritesReady } = useNavFavorites();
  const { top, groups } = visibleNav(ctx);
  const active = activeEntry(pathname);
  const favorites = resolveFavorites(ids, ctx);
  const favoritesOpen = openGroups.has(FAVORITES_GROUP_ID);
  const root = useRef<HTMLElement>(null);
  const refocus = useRef<string | null>(null);

  // when the pin button the user pressed disappears (unpinned from the Favorites list), focus goes to a neighbour instead of being lost
  useEffect(() => {
    if (!refocus.current) return;
    const selector = refocus.current;
    refocus.current = null;
    root.current?.querySelector<HTMLElement>(selector)?.focus();
  }, [favorites.length]);

  const pin = (item: NavItem) => {
    const nowPinned = toggle(item.href, item.label);
    if (nowPinned) openGroup(FAVORITES_GROUP_ID); // so the new favorite is visible straight away
  };
  const unpinFromList = (index: number) => {
    const neighbour = favorites[index + 1] ?? favorites[index - 1];
    refocus.current = neighbour ? `[data-favorite-link="${CSS.escape(neighbour.item.href)}"]` : "#nav-favorites-button";
    toggle(favorites[index].item.href, favorites[index].item.label);
  };

  const itemClass = (isActive: boolean) =>
    cn(
      "relative flex items-center rounded-md text-sm font-medium transition-colors",
      expanded ? "gap-3 px-3 py-2" : "mx-auto h-10 w-10 justify-center",
      isActive ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-accent hover:text-accent-foreground"
    );
  const rowLinkClass = (isActive: boolean) =>
    cn("block truncate rounded-md px-3 py-1.5 pr-9 text-sm transition-colors", isActive ? "bg-primary font-medium text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-accent-foreground");

  return (
    <nav ref={root} aria-label="Main navigation" className="space-y-1 px-3 py-3">
      <ul className="space-y-1">
        {top.map((item) => {
          const Icon = item.icon;
          const isActive = active?.item.href === item.href;
          // no star until the account's favorites are read: a press before that could not be saved
          const canPin = expanded && favoritesReady && isPinnable(item.href);
          return (
            <li key={item.href} className="group relative">
              <Link to={item.href} onClick={onNavigate} aria-current={isActive ? "page" : undefined} aria-label={expanded ? undefined : item.label} title={expanded ? undefined : item.label} className={cn(itemClass(isActive), canPin && "pr-10")}>
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                <span className={cn("truncate", !expanded && "sr-only")}>{item.label}</span>
              </Link>
              {canPin && <PinButton item={item} pinned={isPinned(item.href)} onToggle={() => pin(item)} onDark={isActive} />}
            </li>
          );
        })}
      </ul>

      <div className="pt-1" data-testid="favorites-section" data-ready={favoritesReady ? "true" : "false"}>
        <button
          type="button"
          id="nav-favorites-button"
          aria-expanded={expanded ? favoritesOpen : undefined}
          aria-controls={expanded ? "nav-favorites" : undefined}
          aria-label={expanded ? undefined : "Favorites"}
          title={expanded ? undefined : "Favorites"}
          onClick={() => (expanded ? toggleGroup(FAVORITES_GROUP_ID) : onGroupIconClick?.(FAVORITES_GROUP_ID))}
          className={cn(
            "relative flex w-full items-center rounded-md text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
            expanded ? "gap-3 px-3 py-2" : "mx-auto h-10 w-10 justify-center"
          )}
        >
          <Star className={cn("h-4 w-4 shrink-0", favorites.length > 0 && "fill-current text-amber-500")} aria-hidden />
          <span className={cn("flex-1 truncate text-left", !expanded && "sr-only")}>Favorites</span>
          {expanded && favorites.length > 0 && <span className="rounded-full bg-muted px-1.5 text-xs text-muted-foreground">{favorites.length}</span>}
          {expanded && (favoritesOpen ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden /> : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />)}
        </button>
        {expanded && favoritesOpen && (
          <ul id="nav-favorites" aria-labelledby="nav-favorites-button" className="ml-5 mt-1 space-y-0.5 border-l pl-3">
            {!favoritesReady ? null : favorites.length === 0 ? (
              <li className="px-3 py-2 text-xs text-muted-foreground" data-testid="favorites-empty">
                No favorites yet. Use the star beside any page to pin it here.
              </li>
            ) : (
              favorites.map(({ item }, index) => {
                const isActive = active?.item.href === item.href;
                return (
                  <li key={item.href} className="group relative">
                    <Link to={item.href} onClick={onNavigate} data-favorite-link={item.href} aria-current={isActive ? "page" : undefined} className={rowLinkClass(isActive)}>
                      {item.label}
                    </Link>
                    <PinButton item={item} pinned onToggle={() => unpinFromList(index)} onDark={isActive} always />
                  </li>
                );
              })
            )}
          </ul>
        )}
      </div>

      <ul className="space-y-1 pt-1">
        {groups.map(({ group, items }) => {
          const GroupIcon = group.icon;
          const open = openGroups.has(group.id);
          const holdsActive = active?.group?.id === group.id;
          const panelId = `nav-group-${group.id}`;
          return (
            <li key={group.id}>
              <button
                type="button"
                id={`${panelId}-button`}
                aria-expanded={expanded ? open : undefined}
                aria-controls={expanded ? panelId : undefined}
                aria-label={expanded ? undefined : group.title}
                title={expanded ? undefined : group.title}
                data-active-group={holdsActive ? "true" : undefined}
                onClick={() => (expanded ? toggleGroup(group.id) : onGroupIconClick?.(group.id))}
                className={cn(
                  "relative flex w-full items-center rounded-md text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
                  expanded ? "gap-3 px-3 py-2" : "mx-auto h-10 w-10 justify-center",
                  holdsActive ? "bg-accent text-accent-foreground" : "text-foreground"
                )}
              >
                {holdsActive && <span className="absolute -left-3 top-2 h-6 w-1 rounded-r bg-primary" aria-hidden />}
                <GroupIcon className={cn("h-4 w-4 shrink-0", holdsActive && "text-primary")} aria-hidden />
                <span className={cn("flex-1 truncate text-left", !expanded && "sr-only", holdsActive && "font-semibold")}>{group.title}</span>
                {expanded && (open ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden /> : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />)}
              </button>
              {expanded && open && (
                <ul id={panelId} aria-labelledby={`${panelId}-button`} className="ml-5 mt-1 space-y-0.5 border-l pl-3">
                  {items.map((item) => {
                    const isActive = active?.item.href === item.href;
                    return (
                      <li key={item.href} className="group relative">
                        <Link to={item.href} onClick={onNavigate} aria-current={isActive ? "page" : undefined} className={rowLinkClass(isActive)}>
                          {item.label}
                        </Link>
                        {favoritesReady && <PinButton item={item} pinned={isPinned(item.href)} onToggle={() => pin(item)} onDark={isActive} />}
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          );
        })}
      </ul>

      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </nav>
  );
}
