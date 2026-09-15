import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";

import { PageLoader } from "@/components/ui/page-loader";
import { WrongPortalScreen } from "@/features/auth/components/wrong-portal-screen";
import { useHomePortal } from "@/features/auth/lib/use-home-portal";
import { useAuthStore } from "@/store/auth-store";

interface ProtectedRouteProps {
  children: ReactElement;
  /**
   * Permission code required to view this route (e.g. "pentrix.labs.view").
   * Omit for routes that are ownership-gated server-side instead (most of
   * this app's "me" endpoints need no permission at all — see Task 1's
   * RBAC audit) and so should be reachable by any authenticated student.
   * When set and the user's permission list (fetched on login, see
   * features/auth/api/auth-hooks.ts) doesn't include it, the route is
   * never rendered — the nav link isn't shown either
   * (layouts/app-layout.tsx filters the same way), so this only fires on a
   * stale bookmark or a typed-in URL, not a normal click path.
   */
  permission?: string;
}

export function ProtectedRoute({ children, permission }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const permissions = useAuthStore((state) => state.permissions);
  const { data: homePortal, isLoading } = useHomePortal(isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (isLoading) {
    return <PageLoader />;
  }

  // Beyond mere authentication: does this account's real access actually
  // belong on the Student Portal at all? See portal-resolution.ts for why
  // one login can reach every ERPX subdomain but only be *for* one of
  // them. Checked before the per-route `permission` gate below — a
  // student-only page's specific permission check is meaningless for an
  // account that isn't a student in the first place.
  if (homePortal !== "student") {
    return <WrongPortalScreen target={homePortal ?? null} />;
  }

  if (permission && !permissions.includes(permission)) {
    return <Navigate to="/" replace />;
  }

  return children;
}
