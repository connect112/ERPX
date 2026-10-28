import { createContext, useContext } from "react";

/**
 * What the signed-in person may do on the internship being viewed. An administrator may do everything; an instructor (a
 * trainer given access for a period) may do everything except delete. The server enforces this on every request; the
 * screens use it only to hide controls that would be refused.
 */
export interface InternshipAccess {
  role: "admin" | "instructor";
  canDelete: boolean;
  accessUntil: string | null;
}

export const InternshipAccessContext = createContext<InternshipAccess>({ role: "admin", canDelete: true, accessUntil: null });

export function useInternshipAccess(): InternshipAccess {
  return useContext(InternshipAccessContext);
}

export function useCanDelete(): boolean {
  return useContext(InternshipAccessContext).canDelete;
}

/** "Your access ends on 30 Nov 2026", or null when there is no end date. */
export function accessEndsText(until: string | null, now: Date = new Date()): string | null {
  if (!until) return null;
  const end = new Date(until);
  if (Number.isNaN(end.getTime())) return null;
  const date = end.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  return end.getTime() < now.getTime() ? `Access ended on ${date}` : `Your access ends on ${date}`;
}
