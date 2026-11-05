/**
 * Which onboarding screens a staff member sees in an internship. Two top-level tabs:
 * - "Onboarding": day-to-day work on students (status, acceptance, document review, payment checks, refund requests,
 *   LMS access, completion, the manual tools);
 * - "Onboarding Settings": how this internship onboards (mode, fees, payment methods and accounts, refunds, form and
 *   documents, deadlines and reminders, LMS course and access rule, WhatsApp link, templates).
 * Every control lives in exactly one of them. The API checks permissions again on every action; this only decides what
 * is offered.
 */

export type OnboardingMode = "manual" | "automated" | "hybrid";

export interface OnboardingAccess {
  /** Internship administrator (role admin with delete rights): runs settings, templates, the LMS course. */
  isAdmin: boolean;
  /** our_internships.finance.view or .manage: sees payment checks and amounts. */
  canViewFinance: boolean;
  /** our_internships.finance.manage: edits fees and payment accounts, confirms money. */
  canEditFinance: boolean;
}

export const TOP_TABS = { operations: "onboarding", settings: "onboarding-settings" } as const;

/** Controls of the "Onboarding" tab (work on students). */
export const OPERATION_CONTROLS = [
  "students-board",
  "student-detail",
  "document-review",
  "payment-checks",
  "refund-requests",
  "manual-status-table",
  "lms-access-grant",
  "individual-reopen",
] as const;

/** Controls of the "Onboarding Settings" tab (how the internship onboards). */
export const SETTINGS_CONTROLS = [
  "mode",
  "fees-and-late-fees",
  "payment-timing",
  "payment-methods",
  "payment-accounts",
  "refund-policy",
  "form-fields",
  "document-requirements",
  "deadlines-and-reminders",
  "lms-course",
  "lms-access-rule",
  "whatsapp-link",
  "templates",
] as const;

export type OperationSection = "students" | "payments" | "manual";
export type SettingsSection = "general" | "lms-course" | "accounts" | "templates";

/** The Onboarding tab is there for everyone who can open the internship; the settings tab only for those who can change something in it. */
export function topTabs(access: OnboardingAccess): string[] {
  return settingsSections(access).length > 0 ? [TOP_TABS.operations, TOP_TABS.settings] : [TOP_TABS.operations];
}

export function operationSections(access: OnboardingAccess): OperationSection[] {
  return access.canViewFinance ? ["students", "payments", "manual"] : ["students", "manual"];
}

export function settingsSections(access: OnboardingAccess): SettingsSection[] {
  const out: SettingsSection[] = [];
  if (access.isAdmin) out.push("general", "lms-course");
  if (access.canEditFinance) out.push("accounts");
  if (access.isAdmin) out.push("templates");
  return out;
}

/** Self-service actions (sending links, reopening) are offered only to administrators of a self-service internship. */
export function selfServiceActions(access: OnboardingAccess, mode: OnboardingMode | undefined): boolean {
  return access.isAdmin && mode !== undefined && mode !== "manual";
}

export function modeNotice(mode: OnboardingMode | undefined): string {
  if (mode === "manual")
    return "Manual onboarding: staff record each student's reply, verification, payment and LMS access below. Student links are off; change the mode in Onboarding Settings.";
  if (mode === "hybrid") return "Hybrid onboarding: students use their personal link, and staff can still record any step below.";
  if (mode === "automated") return "Automated onboarding: students use their personal link; staff review documents, confirm payments and follow progress here.";
  return "";
}
