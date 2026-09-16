import type { ReactElement } from "react";
import { Navigate } from "react-router-dom";

import { PageLoader } from "@/components/ui/page-loader";
import { WrongPortalScreen } from "@/features/auth/components/wrong-portal-screen";
import { useHomePortal } from "@/features/auth/lib/use-home-portal";
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
 * *different* ERPX subdomain land here already authenticated. Beyond mere
 * authentication, also checks that this account's real access (RBAC
 * role/Trainer/Employee/Student) actually belongs on the Admin Panel at
 * all; see wrong-portal-screen.tsx for what a mismatch shows and
 * portal-resolution.ts for why one login can reach every ERPX subdomain
 * but only be *for* one of them.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { isLoading: isBootstrapping } = useSsoBootstrap(!isAuthenticated);
  const { data: homePortal, isLoading: isResolvingPortal } = useHomePortal(isAuthenticated);

  if (!isAuthenticated) {
    if (isBootstrapping) {
      return <PageLoader />;
    }
    return <Navigate to="/login" replace />;
  }

  if (isResolvingPortal) {
    return <PageLoader />;
  }

  if (homePortal !== "admin") {
    return <WrongPortalScreen target={homePortal ?? null} />;
  }

  return children;
}
