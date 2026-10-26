import { describe, expect, it } from "vitest";

import type { Attendee } from "@/features/workshop-exams/api/workshop-exams-api";
import { canOpenCertificate, isManualNoShow, needsForcedSend, scoreText } from "@/features/workshop-exams/lib/attendee-state";

const base: Attendee = {
  id: "a1",
  name: "Asha Rao",
  email: "asha@example.com",
  info: {},
  invited_at: null,
  started_at: null,
  submitted_at: null,
  score: null,
  total_marks: null,
  certificate_number: null,
  certificate_sent_at: null,
  certificate_verified_at: null,
  certificate_only: false,
  added_manually: false,
  certificate_forced: false,
  certificate_adjust: null,
};
const manual: Attendee = { ...base, added_manually: true };
const wrote: Attendee = { ...base, started_at: "2026-10-26T10:00:00Z", submitted_at: "2026-10-26T10:20:00Z", score: 3, total_marks: 4 };

describe("manual students who did not attend", () => {
  it("shows Manual - Not attended exam instead of a score", () => {
    expect(isManualNoShow(manual)).toBe(true);
    expect(scoreText(manual)).toBe("Manual - Not attended exam");
  });

  it("keeps the real score once a manual student has written the exam", () => {
    const attended = { ...wrote, added_manually: true };
    expect(isManualNoShow(attended)).toBe(false);
    expect(scoreText(attended)).toBe("3 / 4");
  });

  it("does not label an ordinary student who simply has not started", () => {
    expect(isManualNoShow(base)).toBe(false);
    expect(scoreText(base)).toBe("-");
  });

  it("does not call a manual student who is writing right now a no-show", () => {
    expect(isManualNoShow({ ...manual, started_at: "2026-10-26T10:00:00Z" })).toBe(false);
  });
});

describe("who can have a certificate opened from the mail button", () => {
  it("allows a manual student, someone who wrote the exam, a forced or certificate-only person", () => {
    expect(canOpenCertificate(manual)).toBe(true);
    expect(canOpenCertificate(wrote)).toBe(true);
    expect(canOpenCertificate({ ...base, certificate_forced: true })).toBe(true);
    expect(canOpenCertificate({ ...base, certificate_only: true })).toBe(true);
  });

  it("does not allow a registered student who has not written the exam", () => {
    expect(canOpenCertificate(base)).toBe(false);
  });
});

describe("force sending", () => {
  it("is needed only for a manual student with no exam and no certificate yet", () => {
    expect(needsForcedSend(manual)).toBe(true);
    expect(needsForcedSend({ ...manual, certificate_forced: true })).toBe(false);
    expect(needsForcedSend({ ...manual, submitted_at: "2026-10-26T10:20:00Z" })).toBe(false);
    expect(needsForcedSend(wrote)).toBe(false);
    expect(needsForcedSend(base)).toBe(false);
  });
});
