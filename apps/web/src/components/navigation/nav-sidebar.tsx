import { PanelLeftClose, PanelLeftOpen, Search } from "lucide-react";
import { type FocusEvent, type PointerEvent, type KeyboardEvent as ReactKeyboardEvent, useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";

import { searchableEntries } from "@/components/navigation/access";
import { NavSearchInput, NavSearchPalette, NavSearchResults, useNavSearch } from "@/components/navigation/nav-search";
import { FULL_WIDTH, RAIL_WIDTH, useNavLayout } from "@/components/navigation/nav-state";
import { NavTree } from "@/components/navigation/nav-tree";
import { useNavContext } from "@/components/navigation/use-nav-context";
import { cn } from "@/lib/utils";

/** How long the pointer may be away before a hovered sidebar folds back (so crossing a gap or an edge never flickers it). */
export const LEAVE_DELAY_MS = 140;

const focusVisible = (el: EventTarget | null) => {
  try {
    return el instanceof HTMLElement && el.matches(":focus-visible");
  } catch {
    return true; // an engine without the selector: treat focus as keyboard focus, so the labels are reachable
  }
};

/**
 * The desktop sidebar.
 *
 * - Pinned: full width, and the page makes room for it.
 * - Collapsed: a 64px icon rail that the page makes room for, and nothing more. Moving the pointer onto the rail, or tabbing into it,
 *   opens the full navigation as an overlay ABOVE the page (the page never moves); leaving folds it back after a moment. That is only
 *   a temporary "peek": the saved choice (pinned or collapsed) changes only when the toggle button is used.
 * - A touch screen has no hover: tapping a group icon opens the overlay, and tapping anywhere else closes it.
 */
export function NavSidebar() {
  const { mode, setMode, peek, setPeek, expanded, openGroup, setPaletteOpen, searchInput } = useNavLayout();
  const ctx = useNavContext();
  const navigate = useNavigate();
  const entries = useMemo(() => searchableEntries(ctx), [ctx]);
  const asideRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const pointerInside = useRef(false);
  const focusInside = useRef(false);
  const skipFocusPeek = useRef(false);
  const lastPointer = useRef<string>("mouse");
  const overlay = mode === "collapsed" && peek;
  const search = useNavSearch(entries, (href) => navigate(href));

  const cancel = () => window.clearTimeout(timer.current);
  const foldSoon = () => {
    cancel();
    timer.current = window.setTimeout(() => {
      if (!pointerInside.current && !focusInside.current) setPeek(false);
    }, LEAVE_DELAY_MS);
  };
  useEffect(() => cancel, []);

  // a tap or click anywhere outside folds a temporary sidebar (this is how a touch screen closes it)
  useEffect(() => {
    if (!overlay) return;
    const onDown = (e: globalThis.PointerEvent) => {
      if (asideRef.current && !asideRef.current.contains(e.target as Node)) {
        pointerInside.current = false;
        focusInside.current = false;
        setPeek(false);
      }
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [overlay, setPeek]);

  const onPointerEnter = (e: PointerEvent) => {
    lastPointer.current = e.pointerType;
    if (e.pointerType === "touch") return; // no hover on a touch screen
    pointerInside.current = true;
    cancel();
    if (mode === "collapsed") setPeek(true);
  };
  const onPointerLeave = (e: PointerEvent) => {
    if (e.pointerType === "touch") return;
    pointerInside.current = false;
    if (mode === "collapsed") foldSoon();
  };
  const onFocusIn = (e: FocusEvent) => {
    if (skipFocusPeek.current) {
      skipFocusPeek.current = false;
      return;
    }
    // keyboard focus (and the search box) keeps it open; the focus a mouse click leaves on a link must not
    if (focusVisible(e.target) || (e.target as HTMLElement).tagName === "INPUT") {
      focusInside.current = true;
      cancel();
      if (mode === "collapsed") setPeek(true);
    }
  };
  const onFocusOut = (e: FocusEvent) => {
    if (asideRef.current?.contains(e.relatedTarget as Node | null)) return;
    focusInside.current = false;
    if (mode === "collapsed") foldSoon();
  };
  const onKeyDown = (e: ReactKeyboardEvent) => {
    if (e.key === "Escape" && overlay) {
      cancel();
      pointerInside.current = false;
      focusInside.current = false;
      skipFocusPeek.current = true; // putting focus on the toggle must not reopen what Escape just closed
      setPeek(false);
      toggleRef.current?.focus();
    }
  };
  const afterNavigate = () => {
    // touch and keyboard users have no "leave" to fold the overlay, so choosing a page does it
    if (overlay && lastPointer.current !== "mouse") setPeek(false);
  };

  const pinned = mode === "pinned";
  return (
    <>
      <div className="relative hidden shrink-0 transition-[width] duration-200 motion-reduce:transition-none md:block" style={{ width: pinned ? FULL_WIDTH : RAIL_WIDTH }} data-testid="nav-slot" data-mode={mode}>
        {/* the hover/focus handlers only drive the temporary overlay; every control inside is a real button, link or input */}
        {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
        <aside
          ref={asideRef}
          aria-label="Sidebar"
          data-testid="sidebar"
          data-expanded={expanded ? "true" : "false"}
          data-overlay={overlay ? "true" : "false"}
          onPointerEnter={onPointerEnter}
          onPointerLeave={onPointerLeave}
          onFocus={onFocusIn}
          onBlur={onFocusOut}
          onKeyDown={onKeyDown}
          style={{ width: expanded ? FULL_WIDTH : RAIL_WIDTH }}
          className={cn(
            "absolute inset-y-0 left-0 z-40 flex flex-col overflow-hidden border-r bg-card transition-[width,box-shadow] duration-200 motion-reduce:transition-none",
            overlay && "shadow-2xl"
          )}
        >
          <div className={cn("flex h-16 shrink-0 items-center border-b", expanded ? "justify-between px-4" : "justify-center")}>
            {expanded && <span className="text-lg font-bold tracking-tight">ERPX</span>}
            <button
              ref={toggleRef}
              type="button"
              onClick={() => setMode(pinned ? "collapsed" : "pinned")}
              aria-label={pinned ? "Collapse sidebar" : "Expand sidebar"}
              title={pinned ? "Collapse sidebar" : "Keep sidebar expanded"}
              className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {pinned ? <PanelLeftClose className="h-5 w-5" aria-hidden /> : <PanelLeftOpen className="h-5 w-5" aria-hidden />}
            </button>
          </div>

          <div className={cn("shrink-0", expanded ? "px-3 pt-3" : "flex justify-center pt-3")}>
            {expanded ? (
              <NavSearchInput scope="sidebar" state={search} inputRef={(el) => (searchInput.current = el)} />
            ) : (
              <button
                type="button"
                onClick={() => (setPeek(false), setPaletteOpen(true))}
                aria-label="Search modules"
                title="Search modules"
                className="flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Search className="h-4 w-4" aria-hidden />
              </button>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
            {expanded && search.query.trim() ? (
              <NavSearchResults scope="sidebar" state={search} onPicked={afterNavigate} />
            ) : (
              <NavTree ctx={ctx} expanded={expanded} onNavigate={afterNavigate} onGroupIconClick={(id) => (openGroup(id), setPeek(true))} />
            )}
          </div>
        </aside>
      </div>
      <NavSearchPalette entries={entries} />
    </>
  );
}
