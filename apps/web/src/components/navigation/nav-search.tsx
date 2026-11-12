/* eslint-disable react-refresh/only-export-components -- the hooks and constants live beside the component that provides them */
import { Search } from "lucide-react";
import { type KeyboardEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { SearchEntry } from "@/components/navigation/access";
import { useNavLayout } from "@/components/navigation/nav-state";
import { type SearchResult, highlight, searchNav } from "@/components/navigation/search";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/** Query, results and the highlighted row, with the keys that drive them (arrows, Enter, Escape). Everything is local and instant. */
export function useNavSearch(entries: SearchEntry[], onOpen: (href: string) => void) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const results = useMemo(() => searchNav(entries, query), [entries, query]);
  useEffect(() => setActive(0), [query]);
  const open = (r: SearchResult | undefined) => {
    if (!r) return;
    onOpen(r.entry.item.href);
    setQuery("");
  };
  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" && results.length) {
      e.preventDefault();
      setActive((a) => (a + 1) % results.length);
    } else if (e.key === "ArrowUp" && results.length) {
      e.preventDefault();
      setActive((a) => (a - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      open(results[active]);
    } else if (e.key === "Escape" && query) {
      e.preventDefault();
      e.stopPropagation(); // the first Escape clears the text; a second one closes whatever holds the box
      setQuery("");
    }
  };
  return { query, setQuery, results, active, setActive, open, onKeyDown };
}
export type NavSearchState = ReturnType<typeof useNavSearch>;

const listId = (scope: string) => `nav-search-results-${scope}`;
const optionId = (scope: string, i: number) => `nav-search-option-${scope}-${i}`;

export function NavSearchInput({ scope, state, inputRef, className }: { scope: string; state: NavSearchState; inputRef?: (el: HTMLInputElement | null) => void; className?: string }) {
  return (
    <div className={cn("relative", className)}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
      <input
        ref={inputRef}
        type="text"
        role="combobox"
        aria-label="Search modules"
        aria-expanded={state.query.trim() !== ""}
        aria-controls={listId(scope)}
        aria-activedescendant={state.results.length ? optionId(scope, state.active) : undefined}
        aria-autocomplete="list"
        autoComplete="off"
        spellCheck={false}
        placeholder="Search modules..."
        value={state.query}
        onChange={(e) => state.setQuery(e.target.value)}
        onKeyDown={state.onKeyDown}
        className="h-9 w-full rounded-md border bg-background pl-9 pr-12 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
      />
      <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border bg-muted px-1.5 text-[10px] font-medium text-muted-foreground sm:block" aria-hidden>
        {typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘K" : "Ctrl K"}
      </kbd>
    </div>
  );
}

export function NavSearchResults({ scope, state, onPicked }: { scope: string; state: NavSearchState; onPicked?: () => void }) {
  if (!state.query.trim()) return null;
  if (state.results.length === 0) {
    return (
      <p className="px-3 py-6 text-center text-sm text-muted-foreground" role="status">
        No matching modules
      </p>
    );
  }
  return (
    <ul id={listId(scope)} role="listbox" aria-label="Matching modules" className="space-y-0.5 p-1">
      {state.results.map((r, i) => {
        const Icon = r.entry.item.icon;
        return (
          <li key={r.entry.item.href} id={optionId(scope, i)} role="option" aria-selected={i === state.active}>
            <button
              type="button"
              tabIndex={-1}
              onMouseEnter={() => state.setActive(i)}
              onClick={() => (state.open(r), onPicked?.())}
              className={cn("flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm", i === state.active ? "bg-accent text-accent-foreground" : "hover:bg-accent/60")}
            >
              <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">
                  {highlight(r.entry.item.label, r.ranges).map((p, k) =>
                    p.match ? (
                      <mark key={k} className="bg-transparent font-semibold text-primary underline decoration-primary/40 underline-offset-2">
                        {p.text}
                      </mark>
                    ) : (
                      <span key={k}>{p.text}</span>
                    )
                  )}
                </span>
                {r.entry.groupTitle && <span className="block truncate text-xs text-muted-foreground">{r.entry.groupTitle}</span>}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** The command-palette form of the search: Ctrl/Cmd+K, the rail's Search icon, and the mobile drawer's search button open it. */
export function NavSearchPalette({ entries }: { entries: SearchEntry[] }) {
  const { paletteOpen, setPaletteOpen } = useNavLayout();
  const navigate = useNavigate();
  const state = useNavSearch(entries, (href) => {
    setPaletteOpen(false);
    navigate(href);
  });
  useEffect(() => {
    if (!paletteOpen) state.setQuery("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paletteOpen]);
  return (
    <Dialog open={paletteOpen} onOpenChange={setPaletteOpen}>
      <DialogContent className="top-[18%] max-w-lg translate-y-0 gap-0 p-0">
        <DialogTitle className="sr-only">Search modules</DialogTitle>
        <DialogDescription className="sr-only">Type to find a module you can open. Use the arrow keys and Enter to go to it.</DialogDescription>
        <div className="border-b p-3 pr-12">
          <NavSearchInput scope="palette" state={state} /> {/* the dialog focuses its first field (this one) when it opens */}
        </div>
        <div className="max-h-[50vh] min-h-[3rem] overflow-y-auto" data-testid="palette-results">
          {state.query.trim() ? <NavSearchResults scope="palette" state={state} /> : <p className="px-3 py-6 text-center text-sm text-muted-foreground">Start typing to find a module.</p>}
        </div>
      </DialogContent>
    </Dialog>
  );
}
