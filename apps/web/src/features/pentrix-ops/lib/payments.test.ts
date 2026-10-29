import { describe, expect, it } from "vitest";

import { EMPTY_PAYMENT_FILTERS, paymentParams } from "@/features/pentrix-ops/api/payments-api";
import { PAYMENT_LABEL, addDays, dayLabel, todayIst } from "@/features/pentrix-ops/lib/format";

describe("the payment filters sent to the server", () => {
  it("leaves out whatever is not set and always asks for a sorted page", () => {
    const p = paymentParams({ ...EMPTY_PAYMENT_FILTERS });
    expect([...p.keys()].sort()).toEqual(["order", "page", "page_size", "sort"]);
    expect(p.get("sort")).toBe("date");
  });

  it("sends a status, a candidate and a search as chosen", () => {
    const p = paymentParams({ ...EMPTY_PAYMENT_FILTERS, status: "refunded", q: "INV-1", candidate: "u-1", purpose: "program_fee" });
    expect(Object.fromEntries(p)).toMatchObject({ status: "refunded", q: "INV-1", candidate: "u-1", purpose: "program_fee" });
  });

  it("reads the dates as whole days in India", () => {
    const p = paymentParams({ ...EMPTY_PAYMENT_FILTERS, date_from: "2026-10-20", date_to: "2026-10-20" });
    expect(p.get("date_from")).toBe("2026-10-19T18:30:00.000Z");
    expect(p.get("date_to")).toBe("2026-10-20T18:30:00.000Z"); // up to, not including, midnight after the last day
  });
});

describe("days", () => {
  it("steps over month and year ends", () => {
    expect(addDays("2026-10-29", 3)).toBe("2026-11-01");
    expect(addDays("2026-01-01", -1)).toBe("2025-12-31");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });

  it("writes a day the way people read it, whatever the viewer's own zone", () => {
    expect(dayLabel("2026-10-20")).toMatch(/20 Oct 2026/);
    expect(todayIst()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("has words for every payment status", () => {
    for (const status of ["paid", "pending", "failed", "refunded", "partially_refunded", "none"]) expect(PAYMENT_LABEL[status]).toBeTruthy();
  });
});
