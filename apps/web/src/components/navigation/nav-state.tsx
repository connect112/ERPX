/* eslint-disable react-refresh/only-export-components -- the hooks and constants live beside the component that provides them */
import { type ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import { activeEntry } from "@/components/navigation/access";

/** Saved with the user's browser: how they left the sidebar. Hovering never changes it. */
export type SidebarMode = "pinned" | "collapsed";
export const MODE_KEY = "erpx.nav.mode";
export const GROUPS_KEY = "erpx.nav.groups";
export const RAIL_WIDTH = 64;
export const FULL_WIDTH = 256;

export function readMode(): SidebarMode {
  try {
    return localStorage.getItem(MODE_KEY) === "collapsed" ? "collapsed" : "pinned";
  } catch {
    return "pinned"; // storage can be blocked; the sidebar then simply starts open
  }
}
export function readGroups(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(GROUPS_KEY) ?? "[]") as unknown;
    return Array.isArray(raw) ? raw.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}
function save(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* a blocked store only means the choice is not remembered */
  }
}

interface NavLayout {
  mode: SidebarMode;
  setMode: (m: SidebarMode) => void;
  /** the temporary hover / focus expansion of a collapsed sidebar (never saved) */
  peek: boolean;
  setPeek: (v: boolean) => void;
  /** whether the sidebar currently shows labels: pinned, or peeking */
  expanded: boolean;
  openGroups: ReadonlySet<string>;
  toggleGroup: (id: string) => void;
  openGroup: (id: string) => void;
  mobileOpen: boolean;
  setMobileOpen: (v: boolean) => void;
  paletteOpen: boolean;
  setPaletteOpen: (v: boolean) => void;
  /** the sidebar's own search box, when one is showing, so Ctrl/Cmd+K can focus it */
  searchInput: React.MutableRefObject<HTMLInputElement | null>;
}

const Ctx = createContext<NavLayout | null>(null);

export function useNavLayout(): NavLayout {
  const v = useContext(Ctx);
  if (!v) throw new Error("useNavLayout needs a NavLayoutProvider");
  return v;
}

export function NavLayoutProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const [mode, setModeState] = useState<SidebarMode>(readMode);
  const [peek, setPeek] = useState(false);
  const [open, setOpen] = useState<string[]>(readGroups);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const searchInput = useRef<HTMLInputElement | null>(null);

  const setMode = useCallback((m: SidebarMode) => {
    setModeState(m);
    save(MODE_KEY, m);
    setPeek(false);
  }, []);
  const toggleGroup = useCallback((id: string) => {
    setOpen((cur) => {
      const next = cur.includes(id) ? cur.filter((g) => g !== id) : [...cur, id];
      save(GROUPS_KEY, JSON.stringify(next));
      return next;
    });
  }, []);
  const openGroup = useCallback((id: string) => {
    setOpen((cur) => {
      if (cur.includes(id)) return cur;
      const next = [...cur, id];
      save(GROUPS_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  // the group that holds the current page is always opened when you arrive on it (others you opened stay as they are)
  useEffect(() => {
    const group = activeEntry(pathname)?.group;
    if (group) openGroup(group.id);
  }, [pathname, openGroup]);
  // a drawer or palette never outlives the page you chose in it
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const value = useMemo<NavLayout>(
    () => ({
      mode, setMode, peek, setPeek, expanded: mode === "pinned" || peek, openGroups: new Set(open), toggleGroup, openGroup,
      mobileOpen, setMobileOpen, paletteOpen, setPaletteOpen, searchInput,
    }),
    [mode, setMode, peek, open, toggleGroup, openGroup, mobileOpen, paletteOpen]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
