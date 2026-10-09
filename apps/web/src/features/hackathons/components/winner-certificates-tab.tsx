import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, ChevronDown, ChevronUp, ClipboardCheck, Send } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { type AwardInfo, type AwardPlan, type HackathonPublic, hackathonsApi } from "@/features/hackathons/api/hackathons-api";
import { CertificateDesigner } from "@/features/workshop-exams/components/certificate-designer";
import { CertificateReviewDialog } from "@/features/workshop-exams/components/certificate-review-dialog";
import { workshopExamsApi } from "@/features/workshop-exams/api/workshop-exams-api";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

/** The wording of the automatic certificate, used only until a design image is uploaded for this place. */
function AutomaticWording({ examId }: { examId: string }) {
  const queryClient = useQueryClient();
  const exam = useQuery({ queryKey: ["workshop-exams", examId], queryFn: () => workshopExamsApi.get(examId) });
  const [heading, setHeading] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      workshopExamsApi.update(examId, {
        certificate_heading: heading ?? exam.data?.certificate_heading,
        certificate_text: text ?? exam.data?.certificate_text ?? null,
      }),
    onSuccess: () => {
      setHeading(null);
      setText(null);
      void queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });
    },
  });
  if (!exam.data || exam.data.has_certificate_template) return null;
  const changed = heading !== null || text !== null;
  return (
    <div className="space-y-2 border-t pt-3">
      <p className="text-sm text-muted-foreground">
        No design uploaded: an automatic certificate with this wording is sent instead.
      </p>
      <Input aria-label="Certificate heading" value={heading ?? exam.data.certificate_heading} onChange={(e) => setHeading(e.target.value)} />
      <Textarea aria-label="Certificate wording" rows={2} value={text ?? exam.data.certificate_text ?? ""} onChange={(e) => setText(e.target.value)} />
      <Button size="sm" variant="outline" disabled={!changed || save.isPending} onClick={() => save.mutate()}>
        Save wording
      </Button>
    </div>
  );
}

function AwardCard({ award }: { award: AwardInfo }) {
  const [open, setOpen] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const exam = useQuery({
    queryKey: ["workshop-exams", award.exam_id],
    queryFn: () => workshopExamsApi.get(award.exam_id),
    enabled: open || reviewing,
  });
  const people = award.teams.flatMap((t) => t.members);
  const winning = award.award !== "participation";

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Award className="h-4 w-4 text-amber-500" />
            {award.label} certificate
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant={award.has_design ? "success" : "secondary"}>{award.has_design ? "Design uploaded" : "Automatic design"}</Badge>
            {award.review_required && <Badge variant="warning">Review required</Badge>}
            {award.sent > 0 && <Badge variant="secondary">{award.sent} sent</Badge>}
          </div>
        </div>
        {winning && (
          <CardDescription>
            {award.teams.length === 0
              ? "No team has this place yet."
              : award.teams
                  .map((t) => `${t.team_name} (${t.score} points, ${t.members.length} member${t.members.length === 1 ? "" : "s"})`)
                  .join("; ")}
            {award.teams.length > 0 &&
              (people.length === 1
                ? " The one member gets a certificate."
                : ` Each of the ${people.length} members gets their own certificate.`)}
          </CardDescription>
        )}
        {!winning && (
          <CardDescription>
            For the other participants, when you tick the participation option above. People on a winning team get their
            winner certificate instead.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => setOpen((v) => !v)}>
            {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            Design, ID format &amp; test
          </Button>
          <Button size="sm" variant="outline" onClick={() => setReviewing(true)}>
            <ClipboardCheck className="h-4 w-4" />
            Review certificates
          </Button>
        </div>
        {open && exam.data && (
          <div className="space-y-4 rounded-md border p-3">
            <CertificateDesigner exam={exam.data} />
            <AutomaticWording examId={award.exam_id} />
          </div>
        )}
        {open && exam.isLoading && <Skeleton className="h-24 w-full" />}
      </CardContent>
      {reviewing && exam.data && <CertificateReviewDialog exam={exam.data} onClose={() => setReviewing(false)} />}
    </Card>
  );
}

function PlanSummary({ plans }: { plans: AwardPlan[] }) {
  return (
    <div className="space-y-3">
      {plans.map((plan) => (
        <div key={plan.award} className="rounded-md border p-3 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium">{plan.label}</span>
            <span className="text-muted-foreground">
              {plan.recipients.length} {plan.recipients.length === 1 ? "person" : "people"}
              {plan.already_sent > 0 && `, ${plan.already_sent} already sent`}
              {plan.no_email > 0 && `, ${plan.no_email} without an email`}
            </span>
          </div>
          {plan.review_required && plan.will_send > 0 && (
            <p className="mt-1 text-xs text-sky-700 dark:text-sky-300">
              Review is on for this certificate: they are added, and emailed only after you check and send them.
            </p>
          )}
          {plan.recipients.length > 0 && (
            <ul className="mt-2 grid gap-x-4 gap-y-0.5 sm:grid-cols-2">
              {plan.recipients.map((r) => (
                <li key={`${r.email}-${r.name}`} className="truncate">
                  {r.name}
                  <span className="text-xs text-muted-foreground"> {r.team_name ? `· ${r.team_name}` : ""} {r.email ? "" : "· no email"}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * Certificates for the winners: one per member of the 1st, 2nd and 3rd place teams, each place with its own design, and
 * optionally a participation certificate for everyone else. Each of the four is a full certificate set-up (design and
 * name position, ID format, review, preview and test emails). The emails themselves are edited under Emails.
 */
export function WinnerCertificatesTab({ hackathon }: { hackathon: HackathonPublic }) {
  const queryClient = useQueryClient();
  const overview = useQuery({
    queryKey: ["hackathons", hackathon.id, "award-certificates"],
    queryFn: () => hackathonsApi.openAwardCertificates(hackathon.id),
  });
  const [participation, setParticipation] = useState(false);
  const [audience, setAudience] = useState<"teams" | "all">("teams");
  const [sending, setSending] = useState(false);

  const body = { include_participation: participation, participation_audience: audience };
  const preview = useQuery({
    queryKey: ["hackathons", hackathon.id, "award-certificates", "preview", participation, audience],
    queryFn: () => hackathonsApi.issueAwardCertificates(hackathon.id, { ...body, confirm: false }),
    enabled: sending,
  });
  const send = useMutation({
    mutationFn: () => hackathonsApi.issueAwardCertificates(hackathon.id, { ...body, confirm: true }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["hackathons", hackathon.id, "award-certificates"] });
      void queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });
    },
  });

  if (overview.isLoading) return <Skeleton className="h-48 w-full" />;
  const data = overview.data;
  if (!data) return <p className="text-sm text-destructive">{errorMessage(overview.error, "Could not load the certificates.")}</p>;
  const winners = data.awards.filter((a) => a.award !== "participation");
  const participationAward = data.awards.find((a) => a.award === "participation");
  const winnerCount = winners.reduce((n, a) => n + a.teams.reduce((m, t) => m + t.members.length, 0), 0);
  const audienceCount = audience === "teams" ? data.participation_in_teams : data.participation_everyone;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Winners' certificates</CardTitle>
          <CardDescription>
            The 1st, 2nd and 3rd place teams come from the leaderboard (teams with equal points share a place). Every
            member of a winning team gets their own certificate, so a team of one gets one and a team of four gets
            four. Give each place its own design below, test it, then send.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5" checked={participation} onChange={(e) => setParticipation(e.target.checked)} />
            <span>Also give a participation certificate to the other participants (uses the Participation design below)</span>
          </label>
          {participation && (
            <div className="ml-6 space-y-1 text-sm">
              <label className="flex items-center gap-2">
                <input type="radio" name="aud" checked={audience === "teams"} onChange={() => setAudience("teams")} />
                Everyone who was in a team ({data.participation_in_teams})
              </label>
              <label className="flex items-center gap-2">
                <input type="radio" name="aud" checked={audience === "all"} onChange={() => setAudience("all")} />
                Everyone who was invited ({data.participation_everyone})
              </label>
              <p className="text-xs text-muted-foreground">People on a winning team get the winner certificate, not this one.</p>
            </div>
          )}
          <Button onClick={() => { send.reset(); setSending(true); }} disabled={winnerCount + (participation ? audienceCount : 0) === 0}>
            <Send className="h-4 w-4" />
            Send certificates...
          </Button>
          {winnerCount === 0 && !participation && (
            <p className="text-sm text-muted-foreground">No team has a place yet: certificates can be sent once teams have scores on the leaderboard.</p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4">
        {winners.map((award) => (
          <AwardCard key={award.award} award={award} />
        ))}
        {participationAward && <AwardCard award={participationAward} />}
      </div>

      {sending && (
        <Dialog open onOpenChange={(open) => !open && setSending(false)}>
          <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Send the certificates</DialogTitle>
              <DialogDescription>Check who gets which certificate, then confirm.</DialogDescription>
            </DialogHeader>
            {send.isSuccess ? (
              <div className="space-y-3">
                <p className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">{send.data.message}</p>
                <PlanSummary plans={send.data.awards} />
                <Button variant="outline" onClick={() => setSending(false)}>Close</Button>
              </div>
            ) : preview.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : preview.data ? (
              <div className="space-y-3">
                <PlanSummary plans={preview.data.awards} />
                {send.isError && <p className="text-sm text-destructive">{errorMessage(send.error, "Could not send.")}</p>}
                <div className="flex gap-2">
                  <Button disabled={send.isPending || preview.data.awards.every((p) => p.will_send === 0)} onClick={() => send.mutate()}>
                    {send.isPending ? "Working..." : "Confirm and send"}
                  </Button>
                  <Button variant="outline" onClick={() => setSending(false)}>Cancel</Button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-destructive">{errorMessage(preview.error, "Could not prepare the list.")}</p>
            )}
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
