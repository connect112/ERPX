import { describe, expect, it } from "vitest";

import { pad2, splitDuration, timerState } from "@/features/hackathons/lib/countdown";

const T = (iso: string) => Date.parse(iso);

describe("timerState", () => {
  const start = "2026-10-07T10:00:00Z";
  const end = "2026-10-07T18:00:00Z";

  it("is nothing when no time is set", () => {
    expect(timerState(null, null, T("2026-10-07T09:00:00Z"))).toEqual({ phase: "none", msLeft: null });
  });

  it("counts down to the start, then to the end, then stops", () => {
    expect(timerState(start, end, T("2026-10-07T09:00:00Z"))).toEqual({ phase: "before", msLeft: 3600_000 });
    expect(timerState(start, end, T("2026-10-07T10:00:00Z"))).toEqual({ phase: "running", msLeft: 8 * 3600_000 });
    expect(timerState(start, end, T("2026-10-07T17:59:59Z"))).toEqual({ phase: "running", msLeft: 1000 });
    expect(timerState(start, end, T("2026-10-07T18:00:00Z"))).toEqual({ phase: "ended", msLeft: null });
  });

  it("works with only an end time, or only a start time", () => {
    expect(timerState(null, end, T("2026-10-07T12:00:00Z"))).toEqual({ phase: "running", msLeft: 6 * 3600_000 });
    expect(timerState(null, end, T("2026-10-08T00:00:00Z")).phase).toBe("ended");
    expect(timerState(start, null, T("2026-10-07T09:00:00Z")).phase).toBe("before");
    expect(timerState(start, null, T("2026-10-07T11:00:00Z"))).toEqual({ phase: "running", msLeft: null });
  });

  it("ignores a time it cannot read", () => {
    expect(timerState("not a date", null, Date.now()).phase).toBe("none");
  });
});

describe("splitDuration", () => {
  it("splits into days, hours, minutes and seconds", () => {
    expect(splitDuration(((1 * 24 + 2) * 3600 + 3 * 60 + 4) * 1000)).toEqual({ days: 1, hours: 2, minutes: 3, seconds: 4 });
    expect(splitDuration(59_000)).toEqual({ days: 0, hours: 0, minutes: 0, seconds: 59 });
  });

  it("rounds a part-second up and never goes negative", () => {
    expect(splitDuration(1)).toEqual({ days: 0, hours: 0, minutes: 0, seconds: 1 });
    expect(splitDuration(-5000)).toEqual({ days: 0, hours: 0, minutes: 0, seconds: 0 });
  });

  it("pads for a clock face", () => {
    expect([pad2(0), pad2(7), pad2(45)]).toEqual(["00", "07", "45"]);
  });
});
