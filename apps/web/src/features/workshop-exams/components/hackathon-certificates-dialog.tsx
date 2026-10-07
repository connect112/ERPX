import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useHackathonsList } from "@/features/hackathons/api/hackathons-hooks";
import {
  type HackathonAudience,
  type RecipientStatus,
  type WorkshopExam,
  workshopExamsApi,
} from "@/features/workshop-exams/api/workshop-exams-api";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

const AUDIENCES: { value: HackathonAudience; label: string; hint: string }[] = [
  { value: "all", label: "Everyone invited", hint: "Every participant of the hackathon, with or without a team" },
  { value: "teams", label: "People in a team", hint: "Left out: invited people who never joined a team" },
  { value: "scored", label: "Teams that were scored", hint: "Members of teams with at least one scored task" },
  { value: "top", label: "Top teams", hint: "The best teams by score (ties included), for winner certificates" },
];

const STATUS: Record<RecipientStatus, { label: string; variant: "success" | "info" | "secondary" | "warning" }> = {
  new: { label: "Will be sent", variant: "success" },
  resend: { label: "Will be sent again", variant: "info" },
  already_sent: { label: "Already sent", variant: "secondary" },
  on_exam: { label: "Gets it through the exam", variant: "secondary" },
  no_email: { label: "No email address", variant: "warning" },
};

/**
 * Send this exam's certificate (same design and wording) to the people of a hackathon, from here. It first shows
 * exactly who would get one; nothing is emailed until it is confirmed. Nobody is invited to the exam itself.
 */
export function HackathonCertificatesDialog({ exam, onClose }: { exam: WorkshopExam; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { data: hackathons } = useHackathonsList({ limit: 100 });
  const [hackathonId, setHackathonId] = useState("");
  const [audience, setAudience] = useState<HackathonAudience>("all");
  const [topN, setTopN] = useState("3");

  const topCount = Number(topN);
  const topValid = Number.isInteger(topCount) && topCount >= 1 && topCount <= 50;
  const ready = hackathonId !== "" && (audience !== "top" || topValid);

  const send = useMutation({
    mutationFn: () =>
      workshopExamsApi.hackathonCertificates(exam.id, {
        hackathon_id: hackathonId,
        audience,
        top_n: audience === "top" ? topCount : undefined,
        confirm: true,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workshop-exams"] }),
  });

  const preview = useQuery({
    queryKey: ["workshop-exams", exam.id, "hackathon-certificates", hackathonId, audience, audience === "top" ? topCount : 0],
    queryFn: () =>
      workshopExamsApi.hackathonCertificates(exam.id, {
        hackathon_id: hackathonId,
        audience,
        top_n: audience === "top" ? topCount : undefined,
        confirm: false,
      }),
    // Once sent, keep showing what was sent instead of re-asking (the emails are still on their way).
    enabled: ready && !send.isSuccess,
  });

  const sent = send.isSuccess;
  const plan = send.data ?? preview.data;
  const sentMessage = send.data?.message;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Send this certificate to hackathon participants</DialogTitle>
          <DialogDescription>
            Uses this exam's certificate design and wording, with each person's own name printed on it. They are not
            invited to the exam.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="cert-hackathon">Hackathon</Label>
            <select
              id="cert-hackathon"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={hackathonId}
              onChange={(e) => {
                setHackathonId(e.target.value);
                send.reset();
              }}
            >
              <option value="">Choose a hackathon...</option>
              {(hackathons?.items ?? []).map((h) => (
                <option key={h.id} value={h.id}>
                  {h.title}
                </option>
              ))}
            </select>
          </div>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Who should get one?</legend>
            {AUDIENCES.map((a) => (
              <label key={a.value} className="flex items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="cert-audience"
                  className="mt-1"
                  checked={audience === a.value}
                  onChange={() => {
                    setAudience(a.value);
                    send.reset();
                  }}
                />
                <span>
                  {a.label}
                  <span className="block text-xs text-muted-foreground">{a.hint}</span>
                </span>
              </label>
            ))}
            {audience === "top" && (
              <div className="ml-6 flex items-center gap-2 text-sm">
                <Label htmlFor="cert-top">How many top teams</Label>
                <Input
                  id="cert-top"
                  type="number"
                  min={1}
                  max={50}
                  className={`h-9 w-20 ${topN !== "" && !topValid ? "border-destructive" : ""}`}
                  value={topN}
                  onChange={(e) => {
                    setTopN(e.target.value);
                    send.reset();
                  }}
                />
              </div>
            )}
          </fieldset>

          {!ready ? (
            <p className="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">
              Choose a hackathon to see who would receive a certificate.
            </p>
          ) : preview.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : preview.isError || !plan ? (
            <p className="text-sm text-destructive">{errorMessage(preview.error, "Could not load the list.")}</p>
          ) : (
            <div className="space-y-3">
              <p className="text-sm">
                <strong>{plan.will_send}</strong> certificate{plan.will_send === 1 ? "" : "s"} {sent ? "queued" : "will be emailed"} for{" "}
                <strong>{plan.hackathon_title}</strong>.
                {plan.already_sent > 0 && ` ${plan.already_sent} already received one.`}
                {plan.on_exam > 0 && ` ${plan.on_exam} sit this exam and get theirs through it.`}
                {plan.no_email > 0 && ` ${plan.no_email} have no email address.`}
              </p>
              <div className="max-h-72 overflow-y-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-muted/60 text-left text-xs text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 font-medium">Name</th>
                      <th className="px-3 py-2 font-medium">Email</th>
                      <th className="px-3 py-2 font-medium">Team</th>
                      <th className="px-3 py-2 font-medium">What happens</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {plan.recipients.map((r) => (
                      <tr key={`${r.email ?? r.name}`}>
                        <td className="px-3 py-2 font-medium">{r.name}</td>
                        <td className="px-3 py-2 text-muted-foreground">{r.email ?? "-"}</td>
                        <td className="px-3 py-2 text-muted-foreground">{r.team_name ?? "-"}</td>
                        <td className="px-3 py-2">
                          {sent && (r.status === "new" || r.status === "resend") ? (
                            <Badge variant="success">Queued</Badge>
                          ) : (
                            <Badge variant={STATUS[r.status].variant}>{STATUS[r.status].label}</Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                    {plan.recipients.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-3 py-6 text-center text-muted-foreground">
                          Nobody matches this choice.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {exam.certificate_review && !sent && (
            <p className="rounded-md bg-sky-50 p-2 text-sm text-sky-900 dark:bg-sky-950/40 dark:text-sky-200">
              Review is switched on for this exam: these people are added with their certificate ready, but nothing is
              emailed until you check them in Review certificates and send.
            </p>
          )}
          {sentMessage && <p className="rounded-md bg-emerald-50 p-2 text-sm text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">{sentMessage}</p>}
          {send.isError && <p className="text-sm text-destructive">{errorMessage(send.error, "Could not send the certificates.")}</p>}

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              {send.isSuccess ? "Close" : "Cancel"}
            </Button>
            <Button
              disabled={!plan || plan.will_send === 0 || send.isPending || send.isSuccess}
              onClick={() => {
                if (
                  plan &&
                  window.confirm(
                    `Email ${plan.will_send} certificate${plan.will_send === 1 ? "" : "s"} for ${plan.hackathon_title}? Each person gets this exam's certificate with their own name on it. This can't be undone.`
                  )
                ) {
                  send.mutate();
                }
              }}
            >
              <Send className="h-4 w-4" />
              {send.isPending
                ? "Working..."
                : plan
                  ? `${exam.certificate_review ? "Add" : "Send"} ${plan.will_send} certificate${plan.will_send === 1 ? "" : "s"}`
                  : exam.certificate_review
                    ? "Add"
                    : "Send"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
