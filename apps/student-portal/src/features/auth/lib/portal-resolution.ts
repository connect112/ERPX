import { apiClient } from "@/api/client";

export type PortalKind = "admin" | "trainer" | "employee" | "student";

export const PORTAL_URLS: Record<PortalKind, string> = {
  admin: "https://erp.pentrix.in",
  trainer: "https://trainer.pentrix.in",
  employee: "https://staff.pentrix.in",
  student: "https://lms.pentrix.in",
};

export const PORTAL_LABELS: Record<PortalKind, string> = {
  admin: "Admin Panel",
  trainer: "Trainer Portal",
  employee: "Employee Portal",
  student: "Student Portal",
};

/**
 * Every ERPX login is valid on every one of the 4 portal subdomains (they
 * all authenticate against the same erpx_api backend), but an account is
 * only actually *useful* on the portal(s) matching its real access — an
 * RBAC role, a Trainer record, an Employee record, or a Student record.
 * Without this check, someone with e.g. only trainer access who lands on
 * erp.pentrix.in by mistake sees a normal-looking but non-functional
 * admin panel (every action 403s) instead of a clear way back to where
 * they actually belong. Each of the 4 portals' ProtectedRoute calls this
 * once per session and compares the result against its own identity —
 * see wrong-portal-screen.tsx for what a mismatch shows.
 *
 * Priority mirrors how one person's access actually layers in this
 * codebase: holding one of the two roles that actually run the whole
 * org (administrator/super_admin) is the broadest "this is your real
 * working portal" signal, so it wins over merely having a
 * Trainer/Employee/Student record alongside the same login. Every
 * employee — including admins and trainers — has an Employee record
 * too (Trainer is layered ON Employee, not instead of it — see
 * modules/trainers/models.py), so "employee" is deliberately checked
 * after "trainer": someone with trainer access shouldn't be routed to
 * the (also-valid, but not their actual job) employee self-service
 * portal instead.
 *
 * Deliberately narrower than "has any role at all": an org-custom role
 * (ISE, Senior ISE, Accountant, or any future one) is real, meaningful
 * access, but it isn't administrative access, and treating it as such
 * misroutes -- and previously did, for real -- every holder of one of
 * these roles here instead of to the ownership-gated check their
 * actual job matches (e.g. an ISE with a Trainer record should resolve
 * as "trainer", not "admin"). Only "administrator" and "super_admin"
 * -- the two roles meant to run the whole org -- count as the admin
 * signal; anything else falls through to the ownership checks below,
 * same as holding no role at all. This must stay in sync with
 * apps/web's copy of this same function — a mismatch between the two
 * causes an infinite redirect loop (this portal bounces an account to
 * apps/web, whose stricter check bounces it right back).
 */
export async function resolveHomePortal(): Promise<PortalKind | null> {
  try {
    const { data } = await apiClient.get<{ roles: { slug: string }[] }>("/authorization/me");
    const hasAdministrativeRole = data.roles.some(
      (role) => role.slug === "administrator" || role.slug === "super_admin"
    );
    if (hasAdministrativeRole) return "admin";
  } catch {
    // Not resolvable via role — fall through to the ownership-gated checks.
  }
  try {
    await apiClient.get("/trainers/me");
    return "trainer";
  } catch {
    // No linked Trainer record.
  }
  try {
    await apiClient.get("/employees/me");
    return "employee";
  } catch {
    // No linked Employee record.
  }
  try {
    await apiClient.get("/students/me");
    return "student";
  } catch {
    // No linked Student record either — this login has no recognized
    // profile on any portal.
  }
  return null;
}
