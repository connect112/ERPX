import { type ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { type FavoritesScope, favoritesKey, isPinnable, readFavorites, togglePin, writeFavorites } from "@/components/navigation/favorites";
import { useNavScope } from "@/components/navigation/use-nav-scope";

interface FavoritesApi {
  /** the saved route ids of this account's favorites, in pin order (not yet filtered by permission: see resolveFavorites) */
  ids: readonly string[];
  isPinned: (id: string) => boolean;
  /** pins or unpins a page; returns true when it is now pinned */
  toggle: (id: string, label: string) => boolean;
  /** a sentence for screen readers describing the last change */
  announcement: string;
  /** false until this account's favorites have been read (so the list is not shown as empty while the account is still loading) */
  ready: boolean;
}

const Ctx = createContext<FavoritesApi | null>(null);
const NONE: readonly string[] = [];

// eslint-disable-next-line react-refresh/only-export-components -- the hook lives beside its provider
export function useNavFavorites(): FavoritesApi {
  const v = useContext(Ctx);
  if (!v) throw new Error("useNavFavorites needs a NavFavoritesProvider");
  return v;
}

/** Holds the signed-in account's favorites. They are read again whenever the account (user or organization) changes, and in step with other tabs. */
export function NavFavoritesProvider({ children }: { children: ReactNode }) {
  const scope = useNavScope();
  const key = useMemo(() => (scope.ready ? favoritesKey({ userId: scope.userId, organizationId: scope.organizationId }) : null), [scope.ready, scope.userId, scope.organizationId]);
  const fs: FavoritesScope | null = useMemo(() => (scope.ready ? { userId: scope.userId, organizationId: scope.organizationId } : null), [scope.ready, scope.userId, scope.organizationId]);
  // the ids are tagged with the account they belong to, so a switch of account never shows the previous account's pins, even for a frame
  const [state, setState] = useState<{ key: string | null; ids: string[] }>({ key: null, ids: [] });
  const [announcement, setAnnouncement] = useState("");
  const latest = useRef(state);
  latest.current = state;

  useEffect(() => {
    setState({ key, ids: fs ? readFavorites(fs) : [] });
    setAnnouncement("");
  }, [key, fs]);

  useEffect(() => {
    if (!key || !fs) return;
    const onStorage = (e: StorageEvent) => {
      if (e.key === key) setState({ key, ids: readFavorites(fs) });
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [key, fs]);

  const ids = state.key === key ? state.ids : NONE;

  const toggle = useCallback(
    (id: string, label: string) => {
      if (!key || !fs || !isPinnable(id)) return false;
      const current = latest.current.key === key ? latest.current.ids : [];
      const next = togglePin(current, id);
      const nowPinned = next.includes(id);
      writeFavorites(fs, next);
      latest.current = { key, ids: next };
      setState({ key, ids: next });
      setAnnouncement(nowPinned ? `Pinned ${label} to Favorites.` : `Unpinned ${label} from Favorites.`);
      return nowPinned;
    },
    [key, fs]
  );

  const ready = key !== null && state.key === key;
  const value = useMemo<FavoritesApi>(() => ({ ids, isPinned: (id) => ids.includes(id), toggle, announcement, ready }), [ids, toggle, announcement, ready]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
