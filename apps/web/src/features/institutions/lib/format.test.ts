import { describe, expect, it } from "vitest";

import { errorMessage, eventStatusBadge, eventTypeLabels, formatBytes, formatDateRange, formatDay } from "./format";

describe("formatDay", () => {
  it("shows a calendar day as that day, whatever the reader's time zone", () => {
    // 1 Jan must never become 31 Dec because the reader is west of UTC
    expect(formatDay("2026-01-01")).toBe("1 Jan 2026");
    expect(formatDay("2026-11-10")).toBe("10 Nov 2026");
    expect(formatDay("2028-02-29")).toBe("29 Feb 2028");
  });

  it("leaves something that is not a date as it was", () => {
    expect(formatDay("soon")).toBe("soon");
    expect(formatDay("")).toBe("");
  });
});

describe("formatDateRange", () => {
  it("shows a single day once and a span with both ends", () => {
    expect(formatDateRange("2026-11-10", "2026-11-10")).toBe("10 Nov 2026");
    expect(formatDateRange("2026-11-10", "2026-11-12")).toBe("10 Nov 2026 – 12 Nov 2026");
  });
});

describe("formatBytes", () => {
  it("is empty for no size, KB below a megabyte (never 0 KB) and MB above", () => {
    expect(formatBytes(null)).toBe("");
    expect(formatBytes(10)).toBe("1 KB");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});

describe("errorMessage", () => {
  const failure = (error: unknown) => ({ response: { data: { error } } });

  it("prefers the first validation detail, without pydantic's 'Value error,' prefix", () => {
    expect(errorMessage(failure({ message: "Validation failed", details: [{ msg: "Value error, The end date cannot be before the start date." }] }), "x")).toBe(
      "The end date cannot be before the start date."
    );
  });

  it("falls back to the server's message, then to the caller's own text", () => {
    expect(errorMessage(failure({ message: "An institution with that name and location already exists." }), "x")).toBe(
      "An institution with that name and location already exists."
    );
    expect(errorMessage(new Error("network"), "Could not save.")).toBe("Could not save.");
    expect(errorMessage(undefined, "Could not save.")).toBe("Could not save.");
  });
});

describe("labels", () => {
  it("has a label and a badge for every event type and status the API can return", () => {
    expect(Object.keys(eventTypeLabels).sort()).toEqual(["exam", "hackathon", "other", "workshop"]);
    expect(Object.keys(eventStatusBadge).sort()).toEqual(["completed", "ongoing", "upcoming"]);
  });
});
