import { describe, expect, it } from "vitest";

import { isStudentOnly, redirectedRecently, studentPortalUrl } from "@/features/auth/lib/student-portal-redirect";

const student = { isStudent: true, isTrainer: false, isEmployee: false, isSuperuser: false, roleSlugs: ["student"] };

describe("isStudentOnly", () => {
  it("is true for a plain student, a participant and a student with no role yet", () => {
    expect(isStudentOnly(student)).toBe(true);
    expect(isStudentOnly({ ...student, roleSlugs: ["hackathon_participant"] })).toBe(true);
    expect(isStudentOnly({ ...student, roleSlugs: [] })).toBe(true);
  });

  it("is false for anyone with a staff, trainer, employee or admin side", () => {
    expect(isStudentOnly({ ...student, isStudent: false })).toBe(false);
    expect(isStudentOnly({ ...student, isTrainer: true })).toBe(false);
    expect(isStudentOnly({ ...student, isEmployee: true })).toBe(false);
    expect(isStudentOnly({ ...student, isSuperuser: true })).toBe(false);
    expect(isStudentOnly({ ...student, roleSlugs: ["student", "administrator"] })).toBe(false);
    expect(isStudentOnly({ ...student, roleSlugs: ["ise"] })).toBe(false);
  });
});

describe("studentPortalUrl", () => {
  it("points the live admin site at the student site and does nothing elsewhere", () => {
    expect(studentPortalUrl("erp.pentrix.in")).toBe("https://lms.pentrix.in");
    expect(studentPortalUrl("localhost")).toBeNull();
    expect(studentPortalUrl("lms.pentrix.in")).toBeNull();
  });
});

describe("redirectedRecently", () => {
  const at = (value: string | null) => ({ getItem: () => value });
  it("is true only within a minute of the last hand-off", () => {
    expect(redirectedRecently(at("1000"), 30_000)).toBe(true);
    expect(redirectedRecently(at("1000"), 70_000)).toBe(false);
    expect(redirectedRecently(at(null), 5)).toBe(false);
    expect(redirectedRecently({ getItem: () => { throw new Error("blocked"); } }, 5)).toBe(false);
  });
});
