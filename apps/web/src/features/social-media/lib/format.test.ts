import { describe, expect, it } from "vitest";

import { errorMessage, formatInZone, toInputValue } from "@/features/social-media/lib/format";

describe("social media time helpers", () => {
  it("shows a stored time in the account timezone, as a datetime-local value", () => {
    expect(toInputValue("2026-11-01T03:30:00+00:00", "Asia/Kolkata")).toBe("2026-11-01T09:00");
    expect(toInputValue("2026-11-01T03:30:00+00:00", "UTC")).toBe("2026-11-01T03:30");
  });

  it("returns an empty value when there is no time", () => {
    expect(toInputValue(null, "UTC")).toBe("");
    expect(formatInZone(null, "UTC")).toBe("");
  });
});

describe("errorMessage", () => {
  it("prefers the API's message and trims pydantic's prefix", () => {
    expect(errorMessage({ response: { data: { error: { message: "Nope" } } } }, "fallback")).toBe("Nope");
    expect(
      errorMessage({ response: { data: { error: { message: "x", details: [{ msg: "Value error, Bad colour" }] } } } }, "fallback"),
    ).toBe("Bad colour");
    expect(errorMessage(new Error("boom"), "fallback")).toBe("fallback");
  });
});
