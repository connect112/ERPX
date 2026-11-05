import { describe, expect, it } from "vitest";

import {
  OPERATION_CONTROLS,
  SETTINGS_CONTROLS,
  TOP_TABS,
  modeNotice,
  operationSections,
  selfServiceActions,
  settingsSections,
  topTabs,
} from "@/features/internship-onboarding/lib/tabs";

const admin = { isAdmin: true, canViewFinance: true, canEditFinance: true };
const instructor = { isAdmin: false, canViewFinance: false, canEditFinance: false };
const financeOnly = { isAdmin: false, canViewFinance: true, canEditFinance: true };
const financeViewer = { isAdmin: false, canViewFinance: true, canEditFinance: false };
const adminWithoutFinance = { isAdmin: true, canViewFinance: false, canEditFinance: false };

describe("onboarding tabs", () => {
  it("never puts a control in both tabs", () => {
    const both = OPERATION_CONTROLS.filter((c) => (SETTINGS_CONTROLS as readonly string[]).includes(c));
    expect(both).toEqual([]);
  });

  it("puts every requested setting in Onboarding Settings and every student action in Onboarding", () => {
    expect(SETTINGS_CONTROLS).toEqual(
      expect.arrayContaining(["mode", "fees-and-late-fees", "payment-timing", "payment-accounts", "refund-policy", "form-fields",
        "document-requirements", "deadlines-and-reminders", "lms-course", "lms-access-rule", "whatsapp-link", "templates"]),
    );
    expect(OPERATION_CONTROLS).toEqual(
      expect.arrayContaining(["students-board", "document-review", "payment-checks", "refund-requests", "manual-status-table", "lms-access-grant"]),
    );
  });

  it("shows the settings tab only to people who can change something in it", () => {
    expect(topTabs(admin)).toEqual([TOP_TABS.operations, TOP_TABS.settings]);
    expect(topTabs(financeOnly)).toEqual([TOP_TABS.operations, TOP_TABS.settings]);
    expect(topTabs(instructor)).toEqual([TOP_TABS.operations]);
    expect(topTabs(financeViewer)).toEqual([TOP_TABS.operations]);
  });

  it("gives each permission its own settings sections", () => {
    expect(settingsSections(admin)).toEqual(["general", "lms-course", "accounts", "templates"]);
    expect(settingsSections(adminWithoutFinance)).toEqual(["general", "lms-course", "templates"]);
    expect(settingsSections(financeOnly)).toEqual(["accounts"]);
    expect(settingsSections(instructor)).toEqual([]);
  });

  it("shows payment checks only to finance staff", () => {
    expect(operationSections(admin)).toEqual(["students", "payments", "manual"]);
    expect(operationSections(financeViewer)).toEqual(["students", "payments", "manual"]);
    expect(operationSections(adminWithoutFinance)).toEqual(["students", "manual"]);
    expect(operationSections(instructor)).toEqual(["students", "manual"]);
  });

  it("offers self-service actions only to administrators of hybrid or automated internships", () => {
    expect(selfServiceActions(admin, "hybrid")).toBe(true);
    expect(selfServiceActions(admin, "automated")).toBe(true);
    expect(selfServiceActions(admin, "manual")).toBe(false);
    expect(selfServiceActions(admin, undefined)).toBe(false);
    expect(selfServiceActions(instructor, "automated")).toBe(false);
  });

  it("explains each mode and points manual internships to the settings tab", () => {
    expect(modeNotice("manual")).toContain("Onboarding Settings");
    expect(modeNotice("hybrid")).toContain("staff can still record");
    expect(modeNotice("automated")).toContain("personal link");
  });
});
