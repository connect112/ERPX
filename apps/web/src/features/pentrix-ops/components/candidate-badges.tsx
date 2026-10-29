import { Badge } from "@/components/ui/badge";
import type { AssessmentLine, BookingLine, PaymentLine } from "@/features/pentrix-ops/api/candidates-api";
import { ASSESSMENT_LABEL, ASSESSMENT_TONE, PAYMENT_LABEL, PAYMENT_TONE, STATUS_TONE, istDate, istTime, qualificationOf } from "@/features/pentrix-ops/lib/format";
import type { BookingStatus } from "@/features/pentrix-ops/api/pentrix-ops-api";

export function AssessmentBadge({ assessment }: { assessment: AssessmentLine }) {
  return (
    <div className="space-y-0.5">
      <Badge variant={ASSESSMENT_TONE[assessment.state]}>{ASSESSMENT_LABEL[assessment.state]}</Badge>
      {assessment.attempts > 0 && (
        <div className="text-xs text-muted-foreground">
          {assessment.attempts} attempt{assessment.attempts === 1 ? "" : "s"}
        </div>
      )}
    </div>
  );
}

export function QualificationBadge({ qualified }: { qualified: boolean | null }) {
  const { label, tone } = qualificationOf(qualified);
  return <Badge variant={tone}>{label}</Badge>;
}

export function BookingBadge({ booking }: { booking: BookingLine | null }) {
  if (!booking) return <span className="text-sm text-muted-foreground">Not booked</span>;
  return (
    <div className="space-y-0.5">
      <Badge variant={STATUS_TONE[booking.status as BookingStatus] ?? "secondary"}>{booking.scheduled ? "Scheduled" : booking.status_label}</Badge>
      {booking.slot_start && (
        <div className="text-xs text-muted-foreground">
          {istDate(booking.slot_start)}, {istTime(booking.slot_start)}
        </div>
      )}
    </div>
  );
}

export function PaymentBadge({ payment }: { payment: PaymentLine }) {
  return <Badge variant={PAYMENT_TONE[payment.status]}>{PAYMENT_LABEL[payment.status]}</Badge>;
}
