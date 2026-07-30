import { Suspense } from "react";
import { Outlet } from "react-router-dom";

import { AppSidebar } from "@/components/app-sidebar";
import { AppTopbar } from "@/components/app-topbar";
import { PageLoader } from "@/components/ui/page-loader";

export function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden">
      <AppSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <AppTopbar />
        <main className="flex-1 overflow-y-auto bg-muted/20">
          {/* Single Suspense boundary for every lazily-loaded route rendered
              into this Outlet (see src/router/index.tsx). */}
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
