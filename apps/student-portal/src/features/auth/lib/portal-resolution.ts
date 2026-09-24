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
 * codebase: an RBAC role (administrator/staff/accountant/...) is the
 * broadest "this is your real working portal" signal, so it wins over
 * merely having a Trainer/Employee/Student record alongside the same
 * login. Every employee — including admins and trainers — has an
 * Employee record too (Trainer is layered ON Employee, not instead of
 * it — see modules/trainers/models.py), so "employee" is deliberately
 * checked after "trainer": someone with trainer access shouldn't be
 * routed to the (also-valid, but not their actual job) employee
 * self-service portal instead.
 */
export async function resolveHomePortal(): Promise<PortalKind | null> {
  try {
    const { data } = await apiClient.get<{ roles: { slug: string }[] }>("/authorization/me");
    if (data.roles.length > 0) return "admin";
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
