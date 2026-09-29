import { NavLink } from "react-router-dom";

import { navSections } from "@/components/nav-config";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import { useIsEmployee } from "@/features/employee-self-service/lib/use-is-employee";
import { useIsTrainer } from "@/features/trainer-self-service/lib/use-is-trainer";
import { cn } from "@/lib/utils";

export function AppSidebar() {
  const { data } = useMyRoles();
  const { isTrainer } = useIsTrainer();
  const { isEmployee } = useIsEmployee();
  const permissions = data?.effective_permissions ?? [];
  const isSuperuser = data?.is_superuser ?? false;
  // Every item is filtered against the caller's real effective_permissions
  // (mirroring apps/student-portal's own sidebar filter) or, for the 3
  // items with no grantable permission at all (Organizations, Database
  // Backups, System Health — all require_superuser()-gated server-side),
  // against is_superuser directly. A "Users"/"Roles"/etc. link an
  // org-custom role (e.g. "ISE") doesn't actually have access to simply
  // disappears instead of being shown-but-403ing. A platform-operator
  // (Super Admin) account holds the zero-permission "super_admin" system
  // role, so every ordinary permission-gated item naturally disappears
  // for it too, leaving only the 3 superuser-only items — same end
  // result as this file's old hardcoded "hide Business Modules for
  // Super Admin" special case, without needing one anymore.
  const isVisible = (item: {
    permission?: string;
    superuserOnly?: boolean;
    ownership?: "trainer" | "employee";
  }) => {
    if (item.superuserOnly) return isSuperuser;
    if (item.ownership === "trainer") return isTrainer;
    if (item.ownership === "employee") return isEmployee;
    if (item.permission) return permissions.includes(item.permission);
    return true;
  };
  const visibleSections = navSections
    .map((section) => ({ ...section, items: section.items.filter(isVisible) }))
    .filter((section) => section.items.length > 0);

  return (
    <aside className="hidden w-64 shrink-0 border-r bg-card md:flex md:flex-col">
      <div className="flex h-16 items-center border-b px-6">
        <span className="text-lg font-bold tracking-tight">ERPX</span>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
        {visibleSections.map((section) => (
          <div key={section.title}>
            <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {section.title}
            </p>
            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = item.icon;
                if (!item.enabled) {
                  return (
                    <div
                      key={item.href}
                      className="flex items-center justify-between rounded-md px-3 py-2 text-sm text-muted-foreground/50"
                      title="Coming soon"
                    >
                      <span className="flex items-center gap-3">
                        <Icon className="h-4 w-4" />
                        {item.label}
                      </span>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                        Soon
                      </span>
                    </div>
                  );
                }
                return (
                  <NavLink
                    key={item.href}
                    to={item.href}
                    end
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-primary text-primary-foreground"
                          : "text-foreground hover:bg-accent hover:text-accent-foreground"
                      )
                    }
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
