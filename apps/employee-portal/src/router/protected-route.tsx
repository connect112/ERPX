import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";

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

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (permission && !permissions.includes(permission)) {
    return <Navigate to="/" replace />;
  }

  return children;
}
