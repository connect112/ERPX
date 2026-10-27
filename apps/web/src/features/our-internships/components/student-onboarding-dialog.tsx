import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, ShieldOff } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import {
  type OfferResponse,
  type PaymentStatus,
  type VerificationStatus,
  onboardingApi,
  ourInternshipsKeys,
} from "@/features/our-internships/api/our-internships-api";
import {
  LMS_LABELS,
  OFFER_RESPONSE_LABELS,
  PAYMENT_LABELS,
  VERIFICATION_LABELS,
  amountText,
  parseAmount,
  stageVariant,
  visibleBlockers,
} from "@/features/our-internships/lib/onboarding";
import { formatMarks, formatScore, formatTeamScore } from "@/features/our-internships/lib/performance";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

/**
 * One selected student's profile: how they did, the offer, and the three onboarding steps. Verification and payment are
 * recorded by hand (payment is checked against the bank, not by the system); LMS access is granted from here once both are
 * done, and the student is emailed how to sign in.
 */
export function StudentOnboardingDialog({ internshipId, studentId, onClose }: { internshipId: string; studentId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const profile = useQuery({ queryKey: ["our-internships", "profile", internshipId, studentId], queryFn: () => onboardingApi.student(internshipId, studentId) });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });
    void queryClient.invalidateQueries({ queryKey: ["our-internships", "profile", internshipId, studentId] });
  };

  const s = profile.data;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{s?.name ?? "Student"}</DialogTitle>
          <DialogDescription>{s ? `${s.email}${s.phone ? ` · ${s.phone}` : ""} · ${s.institution_name}` : "Loading..."}</DialogDescription>
        </DialogHeader>
        {profile.isError && <p className="text-sm text-destructive">Could not load this student.</p>}
        {s && <ProfileBody key={`${s.verification_status}-${s.payment_status}-${s.lms_status}-${s.offer_response}`} internshipId={internshipId} studentId={studentId} s={s} onChanged={refresh} />}
      </DialogContent>
    </Dialog>
  );
}

function ProfileBody({ internshipId, studentId, s, onChanged }: { internshipId: string; studentId: string; s: NonNullable<Awaited<ReturnType<typeof onboardingApi.student>>>; onChanged: () => void }) {
  const [response, setResponse] = useState<OfferResponse>(s.offer_response);
  const [verification, setVerification] = useState<VerificationStatus>(s.verification_status);
  const [note, setNote] = useState(s.verification_note ?? "");
  const [payment, setPayment] = useState<PaymentStatus>(s.payment_status);
  const [amount, setAmount] = useState(amountText(s.payment_amount));
  const [reference, setReference] = useState(s.payment_reference ?? "");
  const [received, setReceived] = useState(s.payment_received_on ?? "");

  const granted = s.lms_status === "granted";
  const parsedAmount = parseAmount(amount);
  const dirty =
    response !== s.offer_response ||
    verification !== s.verification_status ||
    note.trim() !== (s.verification_note ?? "") ||
    payment !== s.payment_status ||
    parsedAmount !== s.payment_amount ||
    reference.trim() !== (s.payment_reference ?? "") ||
    received !== (s.payment_received_on ?? "");

  const save = useMutation({
    mutationFn: () =>
      onboardingApi.update(internshipId, studentId, {
        offer_response: response,
        verification_status: verification,
        verification_note: note.trim() || null,
        payment_status: payment,
        payment_amount: parsedAmount ?? null,
        payment_reference: reference.trim() || null,
        payment_received_on: received || null,
      }),
    onSuccess: onChanged,
  });
  const grant = useMutation({ mutationFn: () => onboardingApi.grant(internshipId, studentId), onSuccess: onChanged });
  const revoke = useMutation({ mutationFn: () => onboardingApi.revoke(internshipId, studentId), onSuccess: onChanged });
  const blockers = visibleBlockers(s);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={stageVariant(s.stage)}>{s.stage_label}</Badge>
        {s.offer_reference && <span className="text-xs text-muted-foreground">Offer {s.offer_reference}</span>}
      </div>

      <section className="rounded-md border p-3 text-sm" aria-label="Results">
        <p className="mb-1 font-medium">Results</p>
        {s.standings.length === 0 && <p className="text-muted-foreground">No results recorded.</p>}
        {s.standings.map((st) => (
          <p key={st.event_id} className="text-xs">
            <span className="font-medium">{st.event_name}</span>: exam {formatMarks(st.exam_score, st.exam_total, st.exam_percent)} · team{" "}
            {st.team ? `${st.team.team_name} ${formatTeamScore(st.team.tasks_scored > 0 ? st.team.score : null, st.team.max_total, st.team.rank)}` : "—"} · individual {formatScore(st.individual_score)}
          </p>
        ))}
      </section>

      <fieldset className="space-y-3 rounded-md border p-3">
        <legend className="px-1 text-sm font-medium">Offer</legend>
        <p className="text-xs text-muted-foreground">
          Letter: {s.offer_status === "sent" ? `sent ${s.offer_sent_at ? new Date(s.offer_sent_at).toLocaleDateString() : ""}` : s.offer_status === "queued" ? "being sent" : s.offer_status === "failed" ? "could not be sent" : "not sent yet"}
        </p>
        <div className="space-y-1">
          <Label htmlFor="ob-response">The student's reply</Label>
          <select id="ob-response" className={selectClass} value={response} onChange={(e) => setResponse(e.target.value as OfferResponse)}>
            {Object.entries(OFFER_RESPONSE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </fieldset>

      <fieldset className="space-y-3 rounded-md border p-3">
        <legend className="px-1 text-sm font-medium">Verification</legend>
        <div className="space-y-1">
          <Label htmlFor="ob-verification">Result of the checks</Label>
          <select id="ob-verification" className={selectClass} value={verification} onChange={(e) => setVerification(e.target.value as VerificationStatus)}>
            {Object.entries(VERIFICATION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="ob-note">
            Note <span className="text-xs text-muted-foreground">(optional)</span>
          </Label>
          <Textarea id="ob-note" rows={2} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
        {s.verified_at && verification === s.verification_status && <p className="text-xs text-muted-foreground">Recorded {new Date(s.verified_at).toLocaleString()}</p>}
      </fieldset>

      <fieldset className="space-y-3 rounded-md border p-3">
        <legend className="px-1 text-sm font-medium">Payment</legend>
        <p className="text-xs text-muted-foreground">Payments are checked by hand. Mark it received once you have confirmed the money.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="ob-payment">Status</Label>
            <select id="ob-payment" className={selectClass} value={payment} onChange={(e) => setPayment(e.target.value as PaymentStatus)}>
              {Object.entries(PAYMENT_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="ob-received">Received on</Label>
            <Input id="ob-received" type="date" value={received} onChange={(e) => setReceived(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ob-amount">Amount</Label>
            <Input id="ob-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} aria-invalid={parsedAmount === undefined} />
            {parsedAmount === undefined && <p className="text-xs text-destructive">Enter an amount like 4999 or 4999.50.</p>}
          </div>
          <div className="space-y-1">
            <Label htmlFor="ob-reference">Receipt or transaction reference</Label>
            <Input id="ob-reference" maxLength={120} value={reference} onChange={(e) => setReference(e.target.value)} />
          </div>
        </div>
        {s.payment_confirmed_at && payment === s.payment_status && <p className="text-xs text-muted-foreground">Confirmed {new Date(s.payment_confirmed_at).toLocaleString()}</p>}
      </fieldset>

      {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save.")}</p>}
      <div className="flex items-center gap-2">
        <Button disabled={!dirty || parsedAmount === undefined || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving..." : dirty ? "Save changes" : "Saved"}
        </Button>
        {dirty && <span className="text-xs text-muted-foreground">Save before granting LMS access: it uses what is saved.</span>}
      </div>

      <fieldset className="space-y-3 rounded-md border p-3">
        <legend className="px-1 text-sm font-medium">LMS access (lms.pentrix.in)</legend>
        <p className="text-sm">
          <Badge variant={granted ? "success" : s.lms_status === "revoked" ? "warning" : "secondary"}>{LMS_LABELS[s.lms_status]}</Badge>
          {granted && s.lms_granted_at && <span className="ml-2 text-xs text-muted-foreground">since {new Date(s.lms_granted_at).toLocaleDateString()}</span>}
        </p>
        {blockers.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-amber-700 dark:text-amber-400">
            {blockers.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        )}
        {!granted && blockers.length === 0 && <p className="text-xs text-muted-foreground">Verification and payment are confirmed. Granting access creates the student's login if they have none, enrols them in the course and emails them how to sign in.</p>}
        {(grant.isError || revoke.isError) && <p className="text-sm text-destructive">{errorMessage(grant.error ?? revoke.error, "Could not do that.")}</p>}
        <div className="flex flex-wrap gap-2">
          {!granted && (
            <Button disabled={blockers.length > 0 || dirty || grant.isPending} onClick={() => grant.mutate()}>
              <KeyRound className="h-4 w-4" />
              {grant.isPending ? "Granting..." : "Grant LMS access"}
            </Button>
          )}
          {granted && (
            <Button
              variant="outline"
              disabled={revoke.isPending}
              onClick={() => {
                if (window.confirm(`Withdraw ${s.name}'s access to the course? Their login stays; you can grant access again later.`)) revoke.mutate();
              }}
            >
              <ShieldOff className="h-4 w-4" />
              Withdraw access
            </Button>
          )}
        </div>
      </fieldset>
    </div>
  );
}
