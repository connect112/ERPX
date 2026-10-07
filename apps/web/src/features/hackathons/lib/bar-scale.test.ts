import { describe, expect, it } from "vitest";

import { barPercent, topScore } from "@/features/hackathons/lib/bar-scale";

describe("bar scale", () => {
  it("makes the leading team's bar full height and the others proportional", () => {
    const scores = [108, 54, 27];
    const top = topScore(scores);
    expect(top).toBe(108);
    expect(scores.map((s) => barPercent(s, top))).toEqual([100, 50, 25]);
  });

  it("shortens everyone else's bar when a team pulls ahead", () => {
    expect(barPercent(50, topScore([50, 40]))).toBe(100);
    expect(barPercent(40, topScore([50, 40]))).toBe(80);
    // Team A jumps to 100: it becomes the full bar and B's shrinks.
    expect(barPercent(100, topScore([100, 40]))).toBe(100);
    expect(barPercent(40, topScore([100, 40]))).toBe(40);
  });

  it("does not depend on the marks available, and copes with nobody having scored", () => {
    expect(barPercent(10, topScore([10]))).toBe(100);
    expect(topScore([])).toBe(1);
    expect(barPercent(0, topScore([0, 0]))).toBe(2);
  });
});
