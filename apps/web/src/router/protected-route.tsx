import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";

import { PageLoader } from "@/components/ui/page-loader";
import { WrongPortalScreen } from "@/features/auth/components/wrong-portal-screen";
import { useHomePortal } from "@/features/auth/lib/use-home-portal";
import { useAuthStore } from "@/store/auth-store";

interface ProtectedRouteProps {
  children: ReactElement;
}

/**
 * Wraps any route that requires authentication. Redirects to /login
 * (added by the Authentication module) if there is no valid session, and
 * — beyond mere authentication — checks that this account's real access
 * (RBAC role/Trainer/Employee/Student) actually belongs on the Admin
 * Panel at all; see wrong-portal-screen.tsx for what a mismatch shows and
 * portal-resolution.ts for why one login can reach every ERPX subdomain
 * but only be *for* one of them.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { data: homePortal, isLoading } = useHomePortal(isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (isLoading) {
    return <PageLoader />;
  }

  if (homePortal !== "admin") {
    return <WrongPortalScreen target={homePortal ?? null} />;
  }

  return children;
}
