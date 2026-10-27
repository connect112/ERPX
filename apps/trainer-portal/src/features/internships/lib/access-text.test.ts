import { describe, expect, it } from "vitest";

import { accessText } from "@/features/internships/lib/access-text";

describe("accessText", () => {
  it("shows the last day of access", () => {
    expect(accessText(new Date(2026, 10, 30, 23, 59).toISOString())).toBe("Access until 30 Nov 2026");
  });
  it("says until removed when there is no end", () => {
    expect(accessText(null)).toBe("Access until removed");
  });
});
