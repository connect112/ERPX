import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";

import { useAuthStore } from "@/store/auth-store";

interface ProtectedRouteProps {
  children: ReactElement;
}

/**
 * Wraps any route that requires authentication. Redirects to /login
 * (added by the Authentication module) if there is no valid session.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
