import { describe, expect, it } from "vitest";

import { MAX_FILE_BYTES, checkFiles, timeLeft } from "@/features/my-internship/lib/format";

const file = (name: string, size: number) => ({ name, size }) as File;

describe("checkFiles", () => {
  it("accepts a few normal files", () => {
    expect(checkFiles([file("a.pdf", 10), file("b.zip", 2000)], 3)).toBeNull();
  });
  it("refuses too many files", () => {
    expect(checkFiles([file("a", 1), file("b", 1)], 1)).toBe("You can attach at most 1 file.");
  });
  it("refuses a file over the size limit and an empty file, naming it", () => {
    expect(checkFiles([file("big.zip", MAX_FILE_BYTES + 1)], 3)).toContain("big.zip is larger than 25 MB");
    expect(checkFiles([file("none.txt", 0)], 3)).toBe("none.txt is empty.");
  });
});

describe("timeLeft", () => {
  const now = new Date("2026-11-20T12:00:00Z");
  it("describes what is left in the largest sensible units", () => {
    expect(timeLeft("2026-11-22T15:00:00Z", now)).toBe("2 days 3 hours");
    expect(timeLeft("2026-11-21T12:00:00Z", now)).toBe("1 day");
    expect(timeLeft("2026-11-20T14:30:00Z", now)).toBe("2 hours 30 minutes");
    expect(timeLeft("2026-11-20T12:05:00Z", now)).toBe("5 minutes");
  });
  it("is null once the time has passed or when there is no deadline", () => {
    expect(timeLeft("2026-11-20T11:00:00Z", now)).toBeNull();
    expect(timeLeft(null, now)).toBeNull();
  });
});
