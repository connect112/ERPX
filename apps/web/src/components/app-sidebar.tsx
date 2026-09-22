import { NavLink } from "react-router-dom";

import { navSections } from "@/components/nav-config";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import { cn } from "@/lib/utils";

export function AppSidebar() {
  const { data } = useMyRoles();
  // Super Admin is the platform-operator role (onboard/offboard tenants —
  // see modules/organizations/routes.py's require_superuser()), not a
  // business user of any one tenant's own data. Business Modules is
  // every tenant-scoped module (CRM, courses, accounting, HR, ...) — none
  // of it is Super Admin's job, so it's hidden entirely for that role
  // rather than shown-but-mostly-403ing.
  const isSuperAdmin = data?.roles.some((r) => r.slug === "super_admin") ?? false;
  // "Users" and "Roles" are per-organization membership/RBAC screens — a
  // platform operator managing dozens of customer organizations has no
  // single "users" or "roles" list of its own to view; that's each
  // organization's own admin's job (see modules/users/routes.py and
  // modules/authorization/routes.py, both now organization-scoped).
  const SUPER_ADMIN_HIDDEN_HREFS = new Set(["/administration/users", "/administration/roles"]);
  const visibleSections = isSuperAdmin
    ? navSections
        .filter((section) => section.title !== "Business Modules")
        .map((section) =>
          section.title === "Administration"
            ? { ...section, items: section.items.filter((item) => !SUPER_ADMIN_HIDDEN_HREFS.has(item.href)) }
            : section
        )
    : navSections;

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
