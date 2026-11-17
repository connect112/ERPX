import { Outlet, useLocation } from "react-router-dom";

import { guardFor, isAllowed } from "@/components/navigation/access";
import { useNavContext } from "@/components/navigation/use-nav-context";
import { PageLoader } from "@/components/ui/page-loader";

/**
 * ProtectedRoute only ever checked "is this account authenticated at all"; the permission rules lived in the sidebar, so any signed-in
 * account (a plain student, an org-custom role with no admin permissions) could still render an admin page by typing its URL, even
 * though the link was hidden. The data was safe (every mutation is permission-checked server-side) but the page rendering at all was
 * confusing. This derives the restriction from components/nav-config.ts, the single list the sidebar, the search and this guard share:
 * the longest gated entry a path equals or sits beneath decides (so /students/:id inherits /students), hidden entries and the
 * `guardOnly` list included. A path with no gated entry (Dashboard, Calendar, account settings...) is open to any signed-in user.
 * Server-side authorization is unchanged and still decides every request.
 */
export function RouteGuard() {
  const location = useLocation();
  const ctx = useNavContext();
  if (ctx.isLoading) return <PageLoader />;

  const guard = guardFor(location.pathname);
  if (guard && !isAllowed(guard, ctx)) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
        <p className="text-lg font-medium">You don't have access to this page</p>
        <p className="text-sm text-muted-foreground">Your account doesn't have the permissions this section requires.</p>
      </div>
    );
  }
  return <Outlet />;
}
