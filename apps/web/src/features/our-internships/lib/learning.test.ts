import { describe, expect, it } from "vitest";

import { fromLocalInput, isPastDeadline, newRowId, rubricTotal, sumScores, toLocalInput } from "@/features/our-internships/lib/learning";

describe("date-time inputs", () => {
  it("round-trips an instant through the local input format", () => {
    const iso = "2026-11-20T09:30:00.000Z";
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso);
  });
  it("treats empty and unreadable values as no date", () => {
    expect(toLocalInput(null)).toBe("");
    expect(toLocalInput("not a date")).toBe("");
    expect(fromLocalInput("")).toBeNull();
    expect(fromLocalInput("garbage")).toBeNull();
  });
});

describe("marks", () => {
  it("adds up a rubric", () => {
    expect(rubricTotal([{ points: 30 }, { points: 20 }])).toBe(50);
    expect(rubricTotal([])).toBe(0);
  });
  it("sums typed marks, counting blanks and junk as zero and avoiding float noise", () => {
    expect(sumScores({ a: "25", b: "", c: "x" })).toBe(25);
    expect(sumScores({ a: "0.1", b: "0.2" })).toBe(0.3);
  });
});

describe("deadlines", () => {
  const now = new Date("2026-11-20T12:00:00Z");
  it("passes only when there is a deadline before now", () => {
    expect(isPastDeadline(null, now)).toBe(false);
    expect(isPastDeadline("2026-11-20T11:59:00Z", now)).toBe(true);
    expect(isPastDeadline("2026-11-20T12:01:00Z", now)).toBe(false);
  });
});

describe("row ids", () => {
  it("never repeats an id already in use", () => {
    expect(newRowId("t", [])).toBe("t1");
    expect(newRowId("t", ["t1", "t2"])).toBe("t3");
    expect(newRowId("t", ["t2"])).toBe("t3");
  });
});
