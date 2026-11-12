import { Suspense } from "react";

import { AppTopbar } from "@/components/app-topbar";
import { NavLayoutProvider } from "@/components/navigation/nav-state";
import { NavSidebar } from "@/components/navigation/nav-sidebar";
import { useNavShortcut } from "@/components/navigation/use-nav-shortcut";
import { PageLoader } from "@/components/ui/page-loader";
import { RouteGuard } from "@/router/route-guard";

function Shell() {
  useNavShortcut();
  return (
    <div className="flex h-screen overflow-hidden">
      {/* pinned: the page makes room for the full sidebar; collapsed: only for the icon rail. A hovered rail opens OVER the page. */}
      <NavSidebar />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <AppTopbar />
        <main className="flex-1 overflow-y-auto bg-muted/20">
          {/* Single Suspense boundary for every lazily-loaded route rendered
              here (see src/router/index.tsx). RouteGuard renders the actual
              <Outlet /> once it's confirmed this account is allowed on the
              current path — see its own docstring for why that check exists
              at all. */}
          <Suspense fallback={<PageLoader />}>
            <RouteGuard />
          </Suspense>
        </main>
      </div>
    </div>
  );
}

export function AppLayout() {
  return (
    <NavLayoutProvider>
      <Shell />
    </NavLayoutProvider>
  );
}
