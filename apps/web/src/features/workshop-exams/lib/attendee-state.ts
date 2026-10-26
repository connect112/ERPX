import type { Attendee } from "@/features/workshop-exams/api/workshop-exams-api";

/** Added by hand ("Add student") and never sat the exam: didn't start it, nothing submitted. */
export function isManualNoShow(a: Attendee): boolean {
  return a.added_manually && !a.started_at && !a.submitted_at;
}

/** Whether a certificate can be looked at or sent for this person: they sat the exam, or were added by hand. */
export function canOpenCertificate(a: Attendee): boolean {
  return a.added_manually || a.certificate_only || a.certificate_forced || a.submitted_at !== null;
}

/** What the Score column shows. A manual student who never attended has no score, so it says so. */
export function scoreText(a: Attendee): string {
  if (isManualNoShow(a)) return "Manual - Not attended exam";
  return a.score != null ? `${a.score} / ${a.total_marks}` : "-";
}

/** Sending a certificate to this person is the admin's explicit choice to give them one without the exam. */
export function needsForcedSend(a: Attendee): boolean {
  return a.added_manually && !a.submitted_at && !a.certificate_forced && !a.certificate_only;
}
