import { ChevronDown, ChevronRight } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { type NavContext, activeEntry, visibleNav } from "@/components/navigation/access";
import { useNavLayout } from "@/components/navigation/nav-state";
import { cn } from "@/lib/utils";

/**
 * The navigation list, used by the desktop sidebar (expanded and icon-only) and by the mobile drawer.
 *
 * The same elements stay mounted whether labels are showing or not: when the sidebar is collapsed the labels are only visually hidden
 * (still read by screen readers) and the group's own icon stands for the group. That keeps keyboard focus where it is when the sidebar
 * opens and closes around it. `expanded` false therefore means "icon rail", never "hidden".
 */
export function NavTree({ ctx, expanded, onNavigate, onGroupIconClick }: { ctx: NavContext; expanded: boolean; onNavigate?: () => void; onGroupIconClick?: (groupId: string) => void }) {
  const { pathname } = useLocation();
  const { openGroups, toggleGroup } = useNavLayout();
  const { top, groups } = visibleNav(ctx);
  const active = activeEntry(pathname);

  const itemClass = (isActive: boolean) =>
    cn(
      "relative flex items-center rounded-md text-sm font-medium transition-colors",
      expanded ? "gap-3 px-3 py-2" : "mx-auto h-10 w-10 justify-center",
      isActive ? "bg-primary text-primary-foreground" : "text-foreground hover:bg-accent hover:text-accent-foreground"
    );

  return (
    <nav aria-label="Main navigation" className="space-y-1 px-3 py-3">
      <ul className="space-y-1">
        {top.map((item) => {
          const Icon = item.icon;
          const isActive = active?.item.href === item.href;
          return (
            <li key={item.href}>
              <Link to={item.href} onClick={onNavigate} aria-current={isActive ? "page" : undefined} aria-label={expanded ? undefined : item.label} title={expanded ? undefined : item.label} className={itemClass(isActive)}>
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                <span className={cn("truncate", !expanded && "sr-only")}>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
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
                      <li key={item.href}>
                        <Link
                          to={item.href}
                          onClick={onNavigate}
                          aria-current={isActive ? "page" : undefined}
                          className={cn(
                            "block truncate rounded-md px-3 py-1.5 text-sm transition-colors",
                            isActive ? "bg-primary font-medium text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                          )}
                        >
                          {item.label}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
