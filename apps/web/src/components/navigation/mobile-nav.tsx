import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Menu, Search, X } from "lucide-react";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { searchableEntries } from "@/components/navigation/access";
import { NavSearchInput, NavSearchResults, useNavSearch } from "@/components/navigation/nav-search";
import { useNavLayout } from "@/components/navigation/nav-state";
import { NavTree } from "@/components/navigation/nav-tree";
import { useNavContext } from "@/components/navigation/use-nav-context";

/** Below 768px there is no sidebar: this button (in the top bar) opens the same navigation as a drawer over the page. */
export function MobileNav() {
  const { mobileOpen, setMobileOpen } = useNavLayout();
  const ctx = useNavContext();
  const navigate = useNavigate();
  const entries = useMemo(() => searchableEntries(ctx), [ctx]);
  const search = useNavSearch(entries, (href) => {
    setMobileOpen(false);
    navigate(href);
  });
  return (
    <DialogPrimitive.Root open={mobileOpen} onOpenChange={setMobileOpen}>
      <DialogPrimitive.Trigger asChild>
        <button type="button" aria-label="Open navigation" className="mr-2 flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground md:hidden">
          <Menu className="h-5 w-5" aria-hidden />
        </button>
      </DialogPrimitive.Trigger>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 md:hidden" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          data-testid="mobile-drawer"
          className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r bg-card shadow-2xl focus:outline-none md:hidden"
        >
          <div className="flex h-16 shrink-0 items-center justify-between border-b px-4">
            <DialogPrimitive.Title className="text-lg font-bold tracking-tight">ERPX</DialogPrimitive.Title>
            <DialogPrimitive.Close className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground" aria-label="Close navigation">
              <X className="h-5 w-5" aria-hidden />
            </DialogPrimitive.Close>
          </div>
          <div className="shrink-0 px-3 pt-3">
            <NavSearchInput scope="drawer" state={search} />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            {search.query.trim() ? <NavSearchResults scope="drawer" state={search} /> : <NavTree ctx={ctx} expanded onNavigate={() => setMobileOpen(false)} />}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** A search button for the top bar on small screens (the shortcut and the rail's icon cover larger ones). */
export function MobileSearchButton() {
  const { setPaletteOpen } = useNavLayout();
  return (
    <button type="button" onClick={() => setPaletteOpen(true)} aria-label="Search modules" className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground md:hidden">
      <Search className="h-5 w-5" aria-hidden />
    </button>
  );
}
