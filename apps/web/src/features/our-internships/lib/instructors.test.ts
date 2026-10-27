import { describe, expect, it } from "vitest";

import { dayEnd, dayStart, periodOk, periodText, toDay } from "@/features/our-internships/lib/instructors";

describe("days", () => {
  it("turns a day into the first and last instants of that day, and back", () => {
    expect(toDay(dayStart("2026-11-30"))).toBe("2026-11-30");
    expect(toDay(dayEnd("2026-11-30"))).toBe("2026-11-30");
    expect(new Date(dayEnd("2026-11-30")!).getTime()).toBeGreaterThan(new Date(dayStart("2026-11-30")!).getTime());
  });
  it("makes the end of a day last until just before the next one starts", () => {
    expect(new Date(dayStart("2026-12-01")!).getTime() - new Date(dayEnd("2026-11-30")!).getTime()).toBeLessThanOrEqual(1);
  });
  it("gives nothing for an empty or malformed day", () => {
    expect(dayStart("")).toBeNull();
    expect(dayEnd("30/11/2026")).toBeNull();
    expect(toDay(null)).toBe("");
    expect(toDay("nope")).toBe("");
  });
});

describe("periodOk", () => {
  it("accepts an end on or after the start, and either left empty", () => {
    expect(periodOk("2026-11-03", "2026-11-30")).toBe(true);
    expect(periodOk("2026-11-03", "2026-11-03")).toBe(true);
    expect(periodOk("", "2026-11-30")).toBe(true);
    expect(periodOk("2026-11-03", "")).toBe(true);
  });
  it("refuses an end before the start", () => {
    expect(periodOk("2026-11-30", "2026-11-03")).toBe(false);
  });
});

describe("periodText", () => {
  it("describes each kind of period", () => {
    expect(periodText(dayStart("2026-11-03"), dayEnd("2026-11-30"))).toBe("3 Nov 2026 to 30 Nov 2026");
    expect(periodText(null, dayEnd("2026-11-30"))).toBe("Until 30 Nov 2026");
    expect(periodText(dayStart("2026-11-03"), null)).toBe("From 3 Nov 2026, until removed");
    expect(periodText(null, null)).toBe("Until removed");
  });
});
