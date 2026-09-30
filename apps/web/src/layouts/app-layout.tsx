import { Suspense } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import { AppTopbar } from "@/components/app-topbar";
import { PageLoader } from "@/components/ui/page-loader";
import { RouteGuard } from "@/router/route-guard";

export function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden">
      <AppSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
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
