/**
 * A student who signs in on the admin site (erp.pentrix.in) belongs on the student site (lms.pentrix.in). This is a
 * one-way hand-off: the student site never sends anyone back here, so the two sites can't bounce an account between
 * them (an earlier version that did both caused a refresh-token race and was removed).
 */

const ONLY_STUDENT_ROLES = new Set(["student", "hackathon_participant"]);
const RECENT_MS = 60_000;
const STORAGE_KEY = "erpx-student-redirected-at";

export interface AccessFacts {
  isStudent: boolean;
  isTrainer: boolean;
  isEmployee: boolean;
  isSuperuser: boolean;
  roleSlugs: string[];
}

/** True for an account whose only home is the student site: a student with no staff, trainer or admin side. */
export function isStudentOnly(facts: AccessFacts): boolean {
  return (
    facts.isStudent &&
    !facts.isTrainer &&
    !facts.isEmployee &&
    !facts.isSuperuser &&
    facts.roleSlugs.every((slug) => ONLY_STUDENT_ROLES.has(slug))
  );
}

/** The student site's address for the site we are on (none for local development, where there is no such site). */
export function studentPortalUrl(hostname: string = window.location.hostname): string | null {
  const configured = import.meta.env.VITE_STUDENT_PORTAL_URL as string | undefined;
  if (configured) return configured;
  return hostname === "erp.pentrix.in" ? "https://lms.pentrix.in" : null;
}

/** Whether we already sent this browser to the student site a moment ago (and it came straight back). */
export function redirectedRecently(storage: Pick<Storage, "getItem"> = window.sessionStorage, now: number = Date.now()): boolean {
  try {
    const at = Number(storage.getItem(STORAGE_KEY));
    return Number.isFinite(at) && at > 0 && now - at < RECENT_MS;
  } catch {
    return false;
  }
}

export function markRedirected(storage: Pick<Storage, "setItem"> = window.sessionStorage, now: number = Date.now()): void {
  try {
    storage.setItem(STORAGE_KEY, String(now));
  } catch {
    // no storage (private window): the one-way hand-off still can't loop, since lms never sends anyone back here
  }
}
