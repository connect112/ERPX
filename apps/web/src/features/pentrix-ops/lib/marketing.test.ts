import { describe, expect, it } from "vitest";

import { EMPTY_FILTERS, candidateParams } from "@/features/pentrix-ops/api/candidates-api";
import { newSendKey, selectionFilters } from "@/features/pentrix-ops/api/marketing-api";

describe("the Registrations filters, as the marketing API wants them", () => {
  it("turns each chosen filter into a list and leaves the rest empty", () => {
    const f = selectionFilters({ ...EMPTY_FILTERS, qualification: "qualified", payment: "not_paid", marketing: "opted_in" });
    expect(f).toMatchObject({ q: null, qualification: ["qualified"], payment: ["not_paid"], marketing: ["opted_in"], assessment: [], booking: [], registered_from: null, registered_to: null });
  });

  it("reads the dates as whole days in India", () => {
    const f = selectionFilters({ ...EMPTY_FILTERS, registered_from: "2026-10-20", registered_to: "2026-10-20" });
    expect(f.registered_from).toBe("2026-10-19T18:30:00.000Z");
    expect(f.registered_to).toBe("2026-10-20T18:30:00.000Z");
  });

  it("asks for the same people the list showed", () => {
    const filters = { ...EMPTY_FILTERS, q: "asha", booking: "not_scheduled", marketing: "opted_in" };
    const list = candidateParams(filters);
    const chosen = selectionFilters(filters);
    expect(list.get("q")).toBe(chosen.q);
    expect(list.getAll("booking")).toEqual(chosen.booking);
    expect(list.getAll("marketing")).toEqual(chosen.marketing);
  });
});

describe("one confirmation, one key", () => {
  it("gives a different key each time and one that is long enough for the server", () => {
    const a = newSendKey();
    const b = newSendKey();
    expect(a).not.toBe(b);
    expect(a.length).toBeGreaterThanOrEqual(8);
  });
});
