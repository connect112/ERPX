import { useEffect } from "react";

import { useNavLayout } from "@/components/navigation/nav-state";

/** Typing inside a rich-text editor (or anything marked data-nav-shortcut-ignore) keeps its own Ctrl/Cmd+K (for example "insert link"). */
function inEditor(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || target.closest("[contenteditable='true'], [data-nav-shortcut-ignore]") !== null;
}

/**
 * Ctrl+K (Windows/Linux) or Cmd+K (Mac) searches the navigation: it focuses the sidebar's search box when the sidebar is open, and
 * otherwise opens the search palette (icon-only sidebar, small screens). It works from anywhere in the app, including text fields.
 */
export function useNavShortcut() {
  const { mode, setPaletteOpen, searchInput } = useNavLayout();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.altKey || e.shiftKey || !(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== "k") return;
      if (inEditor(e.target)) return;
      e.preventDefault();
      const box = searchInput.current;
      const visible = !!box && box.getClientRects().length > 0;
      if (mode === "pinned" && visible) {
        box.focus();
        box.select();
      } else {
        setPaletteOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [mode, setPaletteOpen, searchInput]);
}
