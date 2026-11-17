import { describe, expect, it } from "vitest";

import { LEARNING_TABS, learningTabFromParam } from "@/features/learning/lib/tabs";

describe("the Learning tabs", () => {
  it("are exactly the seven, in this order", () => {
    expect([...LEARNING_TABS]).toEqual(["curriculum", "enrollments", "evaluations", "projects", "discussions", "practicals", "viva"]);
  });

  it("read old links: the three evaluation tabs of a course now live under Evaluations", () => {
    expect(learningTabFromParam("assignments")).toBe("evaluations");
    expect(learningTabFromParam("assessments")).toBe("evaluations");
    expect(learningTabFromParam("exams")).toBe("evaluations");
  });

  it("accept every real tab as it is", () => {
    for (const tab of LEARNING_TABS) expect(learningTabFromParam(tab)).toBe(tab);
  });

  it("ignore anything else, so the page keeps its own tab", () => {
    expect(learningTabFromParam(null)).toBeNull();
    expect(learningTabFromParam("")).toBeNull();
    expect(learningTabFromParam("students")).toBeNull();
    expect(learningTabFromParam("onboarding-settings")).toBeNull();
    expect(learningTabFromParam("__proto__")).toBeNull();
  });
});
