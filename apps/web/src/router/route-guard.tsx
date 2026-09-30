import { Outlet, useLocation } from "react-router-dom";

import { navSections } from "@/components/nav-config";
import { PageLoader } from "@/components/ui/page-loader";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import { useIsEmployee } from "@/features/employee-self-service/lib/use-is-employee";
import { useIsStudent } from "@/features/student-self-service/lib/use-is-student";
import { useIsTrainer } from "@/features/trainer-self-service/lib/use-is-trainer";

/**
 * ProtectedRoute only ever checked "is this account authenticated at
 * all" -- nav-config.ts's permission/ownership/superuserOnly fields
 * were used solely to decide what the *sidebar* shows, never to gate
 * the routes themselves. That meant any authenticated account (a plain
 * student, an org-custom role with no admin permissions at all) could
 * still render any admin page's full UI shell -- including its action
 * buttons -- by navigating to the URL directly, even though the link
 * was correctly hidden from their sidebar. The underlying data was
 * still safe (every mutation is permission-checked server-side
 * regardless), but the page itself rendering at all is confusing and
 * wrong. Found live: a student account landed on the admin Announcements
 * page and saw a "New Announcement" button meant only for admins.
 *
 * Rather than hand-annotate each of the ~130 routes in router/index.tsx
 * with its own permission, this derives the same restriction from
 * nav-config.ts -- the single source of truth the sidebar already
 * reads -- by matching the current path against every gated nav item's
 * href (exact match, or a path segment beneath it, so a detail page
 * like /students/:id inherits its list page's requirement). A path
 * with no matching entry, or a nav item with no permission/ownership/
 * superuserOnly at all (Dashboard, Calendar, account-settings, ...),
 * is left unguarded -- same as today.
 */
const guardedRoutes = navSections
  .flatMap((section) => section.items)
  .filter((item) => item.permission || item.superuserOnly || item.ownership)
  .map((item) => ({
    href: item.href,
    permission: item.permission,
    superuserOnly: item.superuserOnly,
    ownership: item.ownership,
  }))
  // Longest href first, so a more specific section (e.g. /accounting/ledger)
  // is matched before a shorter one that would otherwise also prefix-match.
  .sort((a, b) => b.href.length - a.href.length);

function findGuard(pathname: string) {
  return guardedRoutes.find(
    (route) => pathname === route.href || pathname.startsWith(`${route.href}/`)
  );
}

export function RouteGuard() {
  const location = useLocation();
  const { data, isLoading: rolesLoading } = useMyRoles();
  const { isTrainer, isLoading: trainerLoading } = useIsTrainer();
  const { isEmployee, isLoading: employeeLoading } = useIsEmployee();
  const { isStudent, isLoading: studentLoading } = useIsStudent();

  if (rolesLoading || trainerLoading || employeeLoading || studentLoading) {
    return <PageLoader />;
  }

  const guard = findGuard(location.pathname);
  if (guard) {
    const permissions = data?.effective_permissions ?? [];
    const isSuperuser = data?.is_superuser ?? false;
    const allowed = guard.superuserOnly
      ? isSuperuser
      : guard.ownership === "trainer"
        ? isTrainer
        : guard.ownership === "employee"
          ? isEmployee
          : guard.ownership === "student"
            ? isStudent
            : guard.permission
              ? permissions.includes(guard.permission)
              : true;

    if (!allowed) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
          <p className="text-lg font-medium">You don't have access to this page</p>
          <p className="text-sm text-muted-foreground">
            Your account doesn't have the permissions this section requires.
          </p>
        </div>
      );
    }
  }

  return <Outlet />;
}
