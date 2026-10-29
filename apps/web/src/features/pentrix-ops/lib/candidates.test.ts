import { describe, expect, it } from "vitest";

import { EMPTY_FILTERS, candidateParams } from "@/features/pentrix-ops/api/candidates-api";
import { agoOrDate, duration, percent, qualificationOf, rupees } from "@/features/pentrix-ops/lib/format";

describe("qualification is never guessed", () => {
  it("only says not qualified for someone who took the assessment and missed", () => {
    expect(qualificationOf(true).label).toBe("Qualified");
    expect(qualificationOf(false).label).toBe("Not qualified");
    expect(qualificationOf(null).label).toBe("No result yet");
  });
});

describe("the filters sent to the server", () => {
  it("leaves out whatever is not set and always asks for a sorted page", () => {
    const p = candidateParams({ ...EMPTY_FILTERS });
    expect([...p.keys()].sort()).toEqual(["order", "page", "page_size", "sort"]);
    expect(p.get("sort")).toBe("registered");
    expect(p.get("order")).toBe("desc");
  });

  it("sends each group once, so the groups combine", () => {
    const p = candidateParams({ ...EMPTY_FILTERS, qualification: "qualified", payment: "not_paid", booking: "not_scheduled", q: " asha " });
    expect(p.getAll("qualification")).toEqual(["qualified"]);
    expect(p.getAll("payment")).toEqual(["not_paid"]);
    expect(p.getAll("booking")).toEqual(["not_scheduled"]);
    expect(p.get("q")).toBe(" asha "); // trimmed where it is typed, not here
  });

  it("treats the dates as whole days in India: the first day's start to the day after the last day's start", () => {
    const p = candidateParams({ ...EMPTY_FILTERS, registered_from: "2030-01-07", registered_to: "2030-01-09" });
    expect(p.get("registered_from")).toBe("2030-01-06T18:30:00.000Z"); // 00:00 on the 7th in IST
    expect(p.get("registered_to")).toBe("2030-01-09T18:30:00.000Z"); // up to, not including, 00:00 on the 10th in IST
  });
});

describe("the numbers on the screens", () => {
  it("writes money in rupees, with paise only when there are any", () => {
    expect(rupees(250000)).toMatch(/2,500/);
    expect(rupees(250050)).toMatch(/2,500\.50/);
  });

  it("writes percentages and missing values", () => {
    expect(percent(80)).toBe("80%");
    expect(percent(66.666)).toBe("66.7%");
    expect(percent(null)).toBe("—");
    expect(duration(95)).toBe("1 min 35 s");
    expect(duration(40)).toBe("40 s");
    expect(duration(null)).toBe("—");
  });

  it("says how long ago, then a date", () => {
    expect(agoOrDate(null)).toBe("Never");
    expect(agoOrDate(new Date().toISOString())).toBe("Just now");
    expect(agoOrDate(new Date(Date.now() - 5 * 60_000).toISOString())).toBe("5 min ago");
    expect(agoOrDate(new Date(Date.now() - 3 * 3_600_000).toISOString())).toBe("3 h ago");
    expect(agoOrDate("2020-03-04T10:00:00Z")).toMatch(/4 Mar 2020/);
  });
});
