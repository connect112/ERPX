import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";

const SECTIONS = [
  { to: "/administration/email-templates", label: "Template Library", end: true },
  { to: "/administration/email-templates/create", label: "Create Email", end: false },
  { to: "/administration/email-templates/brands", label: "Brand Profiles", end: false },
  { to: "/administration/email-templates/components", label: "Layouts & Components", end: false },
  { to: "/administration/email-templates/signatures", label: "Signature Manager", end: false },
  { to: "/administration/email-templates/history", label: "Testing & History", end: false },
];

/** Email Studio: one place to design, brand, test and publish every email ERPX sends. */
export function StudioLayout() {
  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Email Studio</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Design, preview and publish the emails ERPX sends. Drafts never reach anyone; only a published template that you choose for an
          ERPX email is used, and emails already sent are never changed.
        </p>
      </div>
      <nav aria-label="Email Studio sections" className="flex flex-wrap gap-1 border-b pb-2">
        {SECTIONS.map((s) => (
          <NavLink
            key={s.to}
            to={s.to}
            end={s.end}
            className={({ isActive }) =>
              cn("rounded-md px-3 py-1.5 text-sm font-medium transition-colors", isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground")
            }
          >
            {s.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
