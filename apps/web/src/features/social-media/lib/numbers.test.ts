import { describe, expect, it } from "vitest";

import { NOT_AVAILABLE, formatChange, formatNumber, formatRate, signed } from "@/features/social-media/lib/numbers";

describe("numbers", () => {
  it("never turns a missing figure into zero", () => {
    expect(formatNumber(null)).toBe(NOT_AVAILABLE);
    expect(formatNumber(undefined)).toBe(NOT_AVAILABLE);
    expect(formatNumber(NaN)).toBe(NOT_AVAILABLE);
    expect(formatRate(null)).toBe(NOT_AVAILABLE);
    expect(signed(null)).toBe(NOT_AVAILABLE);
    expect(formatChange(null)).toBeNull();
  });

  it("keeps a real zero as zero", () => {
    expect(formatNumber(0)).toBe("0");
    expect(formatRate(0)).toBe("0.0%");
  });

  it("formats counts and rates readably", () => {
    expect(formatNumber(12345)).toBe("12,345");
    expect(formatNumber(4.25)).toBe("4.3");
    expect(formatRate(0.0123)).toBe("1.2%");
    expect(formatRate(0.25)).toBe("25%");
  });

  it("describes a change in words and signs a difference", () => {
    expect(formatChange(0.5)).toBe("50% higher than before");
    expect(formatChange(-0.2)).toBe("20% lower than before");
    expect(formatChange(0.001)).toBe("about the same as before");
    expect(signed(30)).toBe("+30");
    expect(signed(-4)).toBe("-4");
  });
});
