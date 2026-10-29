import { describe, expect, it } from "vitest";

import { fromIstInput, istDateTime, istTime, toIstInput } from "@/features/pentrix-ops/lib/format";

describe("times are India Standard Time", () => {
  it("shows an instant as IST whatever the viewer's own zone", () => {
    expect(istTime("2030-01-07T12:30:00Z")).toBe("6:00 PM");
    expect(istDateTime("2030-01-07T12:30:00Z")).toMatch(/7 Jan,? 2030, 6:00 PM IST/);
  });

  it("reads a typed time as IST and writes it back unchanged", () => {
    expect(fromIstInput("2030-01-07T18:00")).toBe("2030-01-07T12:30:00.000Z");
    expect(toIstInput("2030-01-07T12:30:00Z")).toBe("2030-01-07T18:00");
    expect(toIstInput(fromIstInput("2030-06-30T21:30"))).toBe("2030-06-30T21:30");
  });
});
