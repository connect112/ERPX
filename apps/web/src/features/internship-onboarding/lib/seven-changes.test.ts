import { describe, expect, it } from "vitest";

import { blobType, viewerKind } from "@/features/internship-onboarding/lib/documents";
import { EXPIRED_CODE, errorCode, msUntil } from "@/features/internship-onboarding/lib/link-expiry";
import { MOBILE_NOTICE, displayMobile, normalizeMobile } from "@/features/internship-onboarding/lib/mobile";
import { isIdentityDocument, sensitiveHelp } from "@/features/internship-onboarding/lib/sensitive";

describe("mobile numbers", () => {
  it.each(["9876543210", "98765 43210", "98765-43210", "(98765) 43210", "+91 98765 43210", "+919876543210", "919876543210", "09876543210", "  98765   43210 "])(
    "reads %j as 9876543210",
    (typed) => expect(normalizeMobile(typed)).toBe("9876543210"),
  );

  it.each(["", "12345", "987654321", "98765432101", "5876543210", "+44 7911 123456", "abcdefghij", "9876 54321O", "+91", null, undefined])(
    "refuses %j",
    (typed) => expect(normalizeMobile(typed as string | null | undefined)).toBeNull(),
  );

  it("shows the number in two groups and keeps the exact notice wording", () => {
    expect(displayMobile("9876543210")).toBe("98765 43210");
    expect(MOBILE_NOTICE).toBe(
      "Please enter your correct mobile number. This number will be used for payment gateway verification and payment-related communication.",
    );
  });
});

describe("the document viewer", () => {
  it("shows PDF, JPG and PNG in the page and offers everything else as a download", () => {
    expect(viewerKind("application/pdf")).toBe("pdf");
    expect(viewerKind("image/jpeg")).toBe("image");
    expect(viewerKind("image/png; charset=binary")).toBe("image");
    for (const other of ["text/html", "image/svg+xml", "application/zip", "", null, undefined]) expect(viewerKind(other)).toBe("download");
    expect(viewerKind("application/pdf", false)).toBe("download"); // the server said it cannot be shown
  });

  it("never lets a document choose an unsafe type for its temporary URL", () => {
    expect(blobType("pdf", "text/html")).toBe("application/pdf");
    expect(blobType("image", "image/png")).toBe("image/png");
    expect(blobType("image", "text/html")).toBe("image/jpeg");
    expect(blobType("download", "text/html")).toBe("application/octet-stream");
  });
});

describe("the personal link", () => {
  it("reads the error code of the standard error envelope", () => {
    expect(errorCode({ response: { data: { error: { code: EXPIRED_CODE } } } })).toBe("onboarding_link_expired");
    expect(errorCode(new Error("network"))).toBeNull();
    expect(errorCode(undefined)).toBeNull();
  });

  it("counts down to a time, never negative, and ignores unreadable or far-away times", () => {
    const now = Date.parse("2026-11-07T10:00:00Z");
    expect(msUntil("2026-11-07T11:00:00Z", now)).toBe(3_600_000);
    expect(msUntil("2026-11-07T09:00:00Z", now)).toBe(0);
    expect(msUntil("not a time", now)).toBeNull();
    expect(msUntil(null, now)).toBeNull();
    expect(msUntil("2030-01-01T00:00:00Z", now)).toBeNull();
  });
});

describe("the Sensitive document setting", () => {
  it("explains why it is unavailable and recognises an Aadhaar document", () => {
    expect(sensitiveHelp.unavailable).toMatch(/virus scanner/);
    expect(isIdentityDocument({ key: "aadhaar", label: "Card" })).toBe(true);
    expect(isIdentityDocument({ key: "gov", label: "Aadhar card" })).toBe(true);
    expect(isIdentityDocument({ key: "college_id", label: "College ID" })).toBe(false);
  });
});
