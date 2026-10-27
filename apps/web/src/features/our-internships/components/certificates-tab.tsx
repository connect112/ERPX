import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, ChevronDown, ChevronUp, ClipboardCheck, Send } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import {
  type CertificateInfo,
  type CertificateKind,
  type CertificatePlan,
  certificateKeys,
  certificatesApi,
} from "@/features/our-internships/api/certificates-api";
import { formatDateTime } from "@/features/our-internships/lib/learning";
import { DELIVERY, KIND_LABELS, changeable, releaseSummary } from "@/features/our-internships/lib/certificates";
import { workshopExamsApi } from "@/features/workshop-exams/api/workshop-exams-api";
import { CertificateDesigner } from "@/features/workshop-exams/components/certificate-designer";
import { CertificateReviewDialog } from "@/features/workshop-exams/components/certificate-review-dialog";

/** The wording of the automatic certificate, used only until a design image is uploaded. */
function AutomaticWording({ examId }: { examId: string }) {
  const queryClient = useQueryClient();
  const exam = useQuery({ queryKey: ["workshop-exams", examId], queryFn: () => workshopExamsApi.get(examId) });
  const [heading, setHeading] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => workshopExamsApi.update(examId, { certificate_heading: heading ?? exam.data?.certificate_heading, certificate_text: text ?? exam.data?.certificate_text ?? null }),
    onSuccess: () => {
      setHeading(null);
      setText(null);
      void queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });
    },
  });
  if (!exam.data || exam.data.has_certificate_template) return null;
  return (
    <div className="space-y-2 border-t pt-3">
      <p className="text-sm text-muted-foreground">No design uploaded: an automatic certificate with this wording is sent instead.</p>
      <Input aria-label="Certificate heading" value={heading ?? exam.data.certificate_heading} onChange={(e) => setHeading(e.target.value)} />
      <Textarea aria-label="Certificate wording" rows={2} value={text ?? exam.data.certificate_text ?? ""} onChange={(e) => setText(e.target.value)} />
      <Button size="sm" variant="outline" disabled={(heading === null && text === null) || save.isPending} onClick={() => save.mutate()}>
        Save wording
      </Button>
    </div>
  );
}

function KindCard({ info }: { info: CertificateInfo }) {
  const [open, setOpen] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const exam = useQuery({ queryKey: ["workshop-exams", info.exam_id], queryFn: () => workshopExamsApi.get(info.exam_id), enabled: open || reviewing });
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Award className="h-4 w-4 text-amber-500" />
            {info.label} certificate
          </CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={info.has_design ? "success" : "secondary"}>{info.has_design ? "Design uploaded" : "Automatic design"}</Badge>
            {info.review_required && <Badge variant="warning">Review required</Badge>}
            <Badge variant="secondary">{info.eligible_count} eligible</Badge>
            {info.sent_count > 0 && <Badge variant="secondary">{info.sent_count} sent</Badge>}
          </div>
        </div>
        <CardDescription>
          {info.kind === "completion" ? "For students who completed the internship." : "For students who took part but did not complete it."} Each student can get one of the
          two, never both.
        </CardDescription>
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
            <AutomaticWording examId={info.exam_id} />
          </div>
        )}
        {open && exam.isLoading && <Skeleton className="h-24 w-full" />}
      </CardContent>
      {reviewing && exam.data && <CertificateReviewDialog exam={exam.data} onClose={() => setReviewing(false)} />}
    </Card>
  );
}

function PlanSummary({ plans }: { plans: CertificatePlan[] }) {
  return (
    <div className="space-y-3">
      {plans.map((plan) => (
        <div key={plan.kind} className="rounded-md border p-3 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium">{plan.label}</span>
            <span className="text-muted-foreground">
              {plan.recipients.length} {plan.recipients.length === 1 ? "student" : "students"}
              {plan.already_sent > 0 && `, ${plan.already_sent} already sent`}
              {plan.no_email > 0 && `, ${plan.no_email} without an email`}
            </span>
          </div>
          {plan.review_required && plan.will_send > 0 && <p className="mt-1 text-xs text-sky-700 dark:text-sky-300">Review is on: they are added, and emailed only after you check and send them.</p>}
          {plan.recipients.length > 0 && (
            <ul className="mt-2 grid gap-x-4 gap-y-0.5 sm:grid-cols-2">
              {plan.recipients.map((r) => (
                <li key={`${r.email}-${r.name}`} className="truncate">
                  {r.name}
                  <span className="text-xs text-muted-foreground"> {r.status === "already_sent" ? "· already sent" : r.status === "resend" ? "· will be sent again" : ""}</span>
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
 * Participation and completion certificates. Choose which one each student is eligible for (one only), set up the design
 * of each, preview who gets what, then release them. Delivery is tracked per student.
 */
export function CertificatesTab({ internshipId, canManage }: { internshipId: string; canManage: boolean }) {
  const queryClient = useQueryClient();
  const overview = useQuery({ queryKey: certificateKeys.overview(internshipId), queryFn: () => certificatesApi.open(internshipId) });
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [releasing, setReleasing] = useState(false);
  const [kinds, setKinds] = useState<Set<CertificateKind>>(new Set(["participation", "completion"]));
  const kindList = [...kinds].sort() as CertificateKind[];

  const refresh = () => queryClient.invalidateQueries({ queryKey: certificateKeys.overview(internshipId) });
  const choose = useMutation({
    mutationFn: (v: { ids: string[]; kind: CertificateKind | null }) => certificatesApi.setEligibility(internshipId, v.ids, v.kind),
    onSuccess: (data) => {
      queryClient.setQueryData(certificateKeys.overview(internshipId), data);
      setPicked(new Set());
    },
  });
  const preview = useQuery({
    queryKey: certificateKeys.preview(internshipId, kindList.join(",")),
    queryFn: () => certificatesApi.issue(internshipId, kindList, false),
    enabled: releasing && kindList.length > 0,
    gcTime: 0,
  });
  const release = useMutation({
    mutationFn: () => certificatesApi.issue(internshipId, kindList, true),
    onSuccess: () => {
      void refresh();
      void queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });
    },
  });

  if (overview.isLoading) return <Skeleton className="h-48 w-full" />;
  if (overview.isError || !overview.data) return <p className="text-sm text-destructive">{errorMessage(overview.error, "Could not load the certificates.")}</p>;
  const { certificates, rows } = overview.data;
  const toggle = (id: string, on: boolean) => {
    const next = new Set(picked);
    if (on) next.add(id);
    else next.delete(id);
    setPicked(next);
  };
  const ids = changeable(rows, picked);
  const eligibleTotal = rows.filter((r) => r.kind).length;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-2">
        {certificates.map((c) => (
          <KindCard key={c.kind} info={c} />
        ))}
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold">Who gets which certificate</h2>
          {canManage && (
            <Button
              disabled={eligibleTotal === 0}
              onClick={() => {
                release.reset();
                setReleasing(true);
              }}
            >
              <Send className="h-4 w-4" />
              Release certificates...
            </Button>
          )}
        </div>
        {canManage && (
          <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 p-2 text-sm">
            <span className="text-muted-foreground">{picked.size} selected:</span>
            <Button size="sm" variant="outline" disabled={ids.length === 0 || choose.isPending} onClick={() => choose.mutate({ ids, kind: "completion" })}>
              Completion
            </Button>
            <Button size="sm" variant="outline" disabled={ids.length === 0 || choose.isPending} onClick={() => choose.mutate({ ids, kind: "participation" })}>
              Participation
            </Button>
            <Button size="sm" variant="ghost" disabled={ids.length === 0 || choose.isPending} onClick={() => choose.mutate({ ids, kind: null })}>
              Clear
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setPicked(new Set(rows.filter((r) => !r.locked).map((r) => r.selection_id)))}>
              Select all
            </Button>
          </div>
        )}
        {choose.isError && <p className="text-sm text-destructive">{errorMessage(choose.error, "Could not change that.")}</p>}
        {rows.length === 0 ? (
          <p className="rounded-md border p-6 text-center text-sm text-muted-foreground">No students have LMS access yet. Grant it under Onboarding.</p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10" />
                  <TableHead>Student</TableHead>
                  <TableHead>Certificate</TableHead>
                  <TableHead>Delivery</TableHead>
                  <TableHead>Certificate ID</TableHead>
                  <TableHead>Sent</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const delivery = DELIVERY[row.delivery];
                  return (
                    <TableRow key={row.selection_id}>
                      <TableCell>
                        <input
                          type="checkbox"
                          aria-label={`Select ${row.student_name}`}
                          disabled={!canManage || row.locked}
                          checked={picked.has(row.selection_id)}
                          onChange={(e) => toggle(row.selection_id, e.target.checked)}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="font-medium">{row.student_name}</div>
                        <div className="text-xs text-muted-foreground">{row.student_email}</div>
                      </TableCell>
                      <TableCell>{row.kind ? <Badge variant={row.kind === "completion" ? "success" : "info"}>{KIND_LABELS[row.kind]}</Badge> : <span className="text-muted-foreground">-</span>}</TableCell>
                      <TableCell>
                        <Badge variant={delivery.variant}>{delivery.label}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{row.certificate_number ?? "-"}</TableCell>
                      <TableCell>{formatDateTime(row.sent_at)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
        <p className="text-xs text-muted-foreground">Once a student's certificate has been created, their choice is fixed.</p>
      </section>

      {releasing && (
        <Dialog open onOpenChange={(open) => !open && setReleasing(false)}>
          <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Release the certificates</DialogTitle>
              <DialogDescription>Check who gets which certificate, then confirm.</DialogDescription>
            </DialogHeader>
            {release.isSuccess ? (
              <div className="space-y-3">
                <p className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200">{release.data.message}</p>
                <PlanSummary plans={release.data.plans} />
                <Button variant="outline" onClick={() => setReleasing(false)}>
                  Close
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-4 text-sm">
                  {(["participation", "completion"] as CertificateKind[]).map((k) => (
                    <label key={k} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={kinds.has(k)}
                        onChange={(e) => {
                          const next = new Set(kinds);
                          if (e.target.checked) next.add(k);
                          else next.delete(k);
                          setKinds(next);
                        }}
                      />
                      {KIND_LABELS[k]}
                    </label>
                  ))}
                </div>
                {preview.isLoading ? (
                  <Skeleton className="h-32 w-full" />
                ) : preview.data ? (
                  <>
                    <PlanSummary plans={preview.data.plans} />
                    <p className="text-sm text-muted-foreground">{releaseSummary(preview.data.plans)}</p>
                  </>
                ) : (
                  kindList.length > 0 && <p className="text-sm text-destructive">{errorMessage(preview.error, "Could not prepare the list.")}</p>
                )}
                {release.isError && <p className="text-sm text-destructive">{errorMessage(release.error, "Could not release.")}</p>}
                <div className="flex gap-2">
                  <Button disabled={release.isPending || !preview.data || preview.data.plans.every((p) => p.will_send === 0)} onClick={() => release.mutate()}>
                    {release.isPending ? "Working..." : "Confirm and release"}
                  </Button>
                  <Button variant="outline" onClick={() => setReleasing(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
