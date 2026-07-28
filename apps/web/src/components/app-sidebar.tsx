import { NavLink } from "react-router-dom";

import { navSections } from "@/components/nav-config";
import { cn } from "@/lib/utils";

export function AppSidebar() {
  return (
    <aside className="hidden w-64 shrink-0 border-r bg-card md:flex md:flex-col">
      <div className="flex h-16 items-center border-b px-6">
        <span className="text-lg font-bold tracking-tight">ERPX</span>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
        {navSections.map((section) => (
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
