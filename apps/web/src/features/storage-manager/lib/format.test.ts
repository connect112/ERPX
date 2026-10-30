import { describe, expect, it } from "vitest";

import { formatBytes, formatDate, pathLabel, percent, STATUS_LABELS, STATUS_TONES } from "@/features/storage-manager/lib/format";

describe("formatBytes", () => {
  it("keeps small values exact and scales larger ones", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1023)).toBe("1023 B");
    expect(formatBytes(1024)).toBe("1.0 KB");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
    expect(formatBytes(471_384_976)).toBe("450 MB");
    expect(formatBytes(3 * 1024 ** 3)).toBe("3.0 GB");
  });

  it("shows a dash when the size is unknown", () => {
    expect(formatBytes(null)).toBe("—");
    expect(formatBytes(undefined)).toBe("—");
  });
});

describe("formatDate", () => {
  it("shows a dash for missing or invalid dates", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("not a date")).toBe("—");
  });

  it("formats a real timestamp", () => {
    expect(formatDate("2026-10-30T03:30:00Z")).toMatch(/2026/);
  });
});

describe("labels", () => {
  it("has a label and a tone for every file status", () => {
    for (const status of ["in_use", "pending", "orphan", "missing_object", "protected"] as const) {
      expect(STATUS_LABELS[status]).toBeTruthy();
      expect(STATUS_TONES[status]).toBeTruthy();
    }
  });

  it("labels the root folder and joins folders", () => {
    expect(pathLabel([])).toBe("All storage");
    expect(pathLabel(["Object storage", "Documents"])).toBe("Object storage / Documents");
  });

  it("clamps percentages and survives a zero total", () => {
    expect(percent(1, 4)).toBe(25);
    expect(percent(9, 3)).toBe(100);
    expect(percent(5, 0)).toBe(0);
  });
});
