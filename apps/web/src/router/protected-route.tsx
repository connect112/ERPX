import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";

import { StudentPortalRedirect } from "@/components/student-portal-redirect";
import { PageLoader } from "@/components/ui/page-loader";
import { useSsoBootstrap } from "@/features/auth/lib/use-sso-bootstrap";
import { useAuthStore } from "@/store/auth-store";

interface ProtectedRouteProps {
  children: ReactElement;
}

/**
 * Wraps any route that requires authentication. If there's no local
 * session, first tries a silent cross-subdomain login via the shared
 * `erpx_sso` cookie (use-sso-bootstrap.ts) before giving up and redirecting
 * to /login — this is what lets someone who already logged in on a
 * *different* ERPX subdomain land here already authenticated.
 *
 * erp.pentrix.in is the single portal for every role (admin, trainer,
 * employee, student alike) — any authenticated account renders the app
 * shell and sees whatever the sidebar's own permission filtering
 * (app-sidebar.tsx, driven by GET /authorization/me) exposes to them.
 * The one exception is an account that is ONLY a student (no staff, trainer or
 * admin side): it is handed one way to lms.pentrix.in (StudentPortalRedirect),
 * and lms never sends anyone back. Otherwise this deliberately does NOT gate
 * on account "kind" or bounce anyone to another subdomain: the old two-way
 * per-portal-kind redirect (formerly
 * portal-resolution.ts / wrong-portal-screen.tsx here) caused a real,
 * disruptive bug — two portals racing to refresh/rotate the same
 * account's shared SSO cookie concurrently, tripping the refresh-token
 * reuse/theft detection and repeatedly nuking every session for that
 * account, which looked like the browser endlessly bouncing between
 * subdomains. Removed rather than patched again.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { isLoading: isBootstrapping } = useSsoBootstrap(!isAuthenticated);

  if (!isAuthenticated) {
    if (isBootstrapping) {
      return <PageLoader />;
    }
    return <Navigate to="/login" replace />;
  }

  // A student has no business on the admin site: hand them to the student site (one way, see the component).
  return (
    <>
      {children}
      <StudentPortalRedirect />
    </>
  );
}
