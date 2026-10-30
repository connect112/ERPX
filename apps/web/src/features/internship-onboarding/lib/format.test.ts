import { describe, expect, it } from "vitest";

import { fromLocalInput, inZone, money, slugKey, statusLabel, statusTone, tokenFromHash, toLocalInput } from "@/features/internship-onboarding/lib/format";

describe("onboarding format helpers", () => {
  it("formats decimal-string amounts without float maths", () => {
    expect(money("5000.00")).toBe("₹5,000.00");
    expect(money("1234567.5")).toBe("₹1,234,567.50");
    expect(money("-500.00")).toBe("-₹500.00");
    expect(money(null)).toBe("—");
  });

  it("reads the token only from the fragment and only if it looks like one", () => {
    expect(tokenFromHash("#t=abcDEF123_-abcDEF123_-xyz")).toBe("abcDEF123_-abcDEF123_-xyz");
    expect(tokenFromHash("#t=short")).toBeNull();
    expect(tokenFromHash("#t=<script>alert(1)</script>xxxxxxxx")).toBeNull();
    expect(tokenFromHash("")).toBeNull();
  });

  it("round-trips datetime-local values", () => {
    const iso = fromLocalInput("2026-11-15T23:59");
    expect(iso).not.toBeNull();
    expect(toLocalInput(iso)).toBe("2026-11-15T23:59");
    expect(fromLocalInput("")).toBeNull();
  });

  it("shows deadlines in the internship's own time zone", () => {
    const text = inZone("2026-11-15T18:29:00Z", "Asia/Kolkata");
    expect(text).toContain("15 Nov 2026");
    expect(text).toMatch(/11:59\s?pm/i);
    expect(text).toMatch(/IST|GMT\+5:30/);
    expect(inZone(null, "Asia/Kolkata")).toBe("—");
  });

  it("labels and colours statuses", () => {
    expect(statusLabel("awaiting_manual_payment_approval")).toBe("Payment being checked");
    expect(statusTone("completed")).toBe("success");
    expect(statusTone("changes_requested")).toBe("destructive");
    expect(statusTone("awaiting_payment")).toBe("warning");
  });

  it("makes unique field keys", () => {
    const taken = new Set(["t_shirt_size"]);
    expect(slugKey("T-shirt size", taken)).toBe("t_shirt_size_2");
    expect(slugKey("12th marks", new Set())).toBe("f_12th_marks");
  });
});
