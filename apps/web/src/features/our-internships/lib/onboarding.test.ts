import { describe, expect, it } from "vitest";

import type { SelectedStudent } from "@/features/our-internships/api/our-internships-api";

import { amountText, chunk, grantableIds, parseAmount, stageCounts, stageVariant, visibleBlockers } from "./onboarding";

function student(over: Partial<SelectedStudent> & { student_id: string }): SelectedStudent {
  return {
    name: over.student_id,
    email: `${over.student_id}@example.com`,
    phone: null,
    institution_id: "i",
    institution_name: "College",
    note: null,
    selected_at: "2026-11-01T00:00:00Z",
    offer_reference: null,
    offer_status: "not_sent",
    offer_sent_at: null,
    offer_error: null,
    offer_response: "awaiting",
    offer_response_at: null,
    verification_status: "pending",
    verification_note: null,
    verified_at: null,
    payment_status: "pending",
    payment_amount: null,
    payment_reference: null,
    payment_received_on: null,
    payment_confirmed_at: null,
    lms_status: "not_granted",
    lms_granted_at: null,
    stage: "selected",
    stage_label: "Selected",
    grant_blockers: ["Verification is not complete."],
    standings: [],
    ...over,
  };
}

describe("stages", () => {
  it("counts students per stage", () => {
    const items = [student({ student_id: "a" }), student({ student_id: "b" }), student({ student_id: "c", stage: "lms_access" })];
    expect(stageCounts(items)).toEqual({ selected: 2, lms_access: 1 });
  });

  it("colours success, the two ways out and the steps in between differently, and copes with an unknown stage", () => {
    expect(stageVariant("lms_access")).toBe("success");
    expect(stageVariant("declined")).toBe("destructive");
    expect(stageVariant("rejected")).toBe("destructive");
    expect(stageVariant("verified")).toBe("warning");
    expect(stageVariant("something_new")).toBe("secondary");
  });
});

describe("granting access", () => {
  const items = [
    student({ student_id: "ready", grant_blockers: [] }),
    student({ student_id: "blocked" }),
    student({ student_id: "done", lms_status: "granted", grant_blockers: ["LMS access has already been granted."] }),
    student({ student_id: "back", lms_status: "revoked", grant_blockers: [] }),
  ];

  it("offers only students with nothing in the way and no access yet (a student whose access was withdrawn can have it again)", () => {
    expect(grantableIds(items)).toEqual(["ready", "back"]);
  });

  it("does not show 'already granted' as a problem", () => {
    expect(visibleBlockers(items[2])).toEqual([]);
    expect(visibleBlockers(items[1])).toEqual(["Verification is not complete."]);
  });
});

describe("chunk", () => {
  it("splits into batches of at most the size, keeping the order", () => {
    expect(chunk([1, 2, 3, 4, 5], 2)).toEqual([[1, 2], [3, 4], [5]]);
    expect(chunk([], 25)).toEqual([]);
    expect(chunk(Array.from({ length: 60 }, (_, i) => i), 25).map((c) => c.length)).toEqual([25, 25, 10]);
  });
});

describe("amounts", () => {
  it("turns what was typed into an amount: empty is none, two decimals at most, nothing negative or unreadable", () => {
    expect(parseAmount("")).toBeNull();
    expect(parseAmount("  4999.50 ")).toBe(4999.5);
    expect(parseAmount("5000")).toBe(5000);
    expect(parseAmount("0")).toBe(0);
    for (const bad of ["-1", "12.345", "abc", "1,000", "1e3", "."]) expect(parseAmount(bad)).toBeUndefined();
  });

  it("shows an existing amount as text and an empty one as nothing", () => {
    expect(amountText(4999.5)).toBe("4999.5");
    expect(amountText(0)).toBe("0");
    expect(amountText(null)).toBe("");
  });
});
