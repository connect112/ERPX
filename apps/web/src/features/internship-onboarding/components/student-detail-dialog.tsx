import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, Eye, Link2Off } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/features/institutions/lib/format";
import { onboardingFlowApi } from "@/features/internship-onboarding/api";
import { DocumentViewer } from "@/features/internship-onboarding/components/document-viewer";
import { inZone, money, statusLabel, statusTone } from "@/features/internship-onboarding/lib/format";

interface Props {
  internshipId: string;
  studentId: string;
  timezone: string;
  canManage: boolean;
  onClose: () => void;
}

export function StudentDetailDialog({ internshipId, studentId, timezone, canManage, onClose }: Props) {
  const queryClient = useQueryClient();
  const key = ["onboarding-flow", internshipId, "student", studentId];
  const detail = useQuery({ queryKey: key, queryFn: () => onboardingFlowApi.student(internshipId, studentId) });
  const [link, setLink] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["onboarding-flow", internshipId] });
  const fail = (e: unknown) => setError(errorMessage(e, "That did not work."));

  const newLink = useMutation({ mutationFn: () => onboardingFlowApi.newLink(internshipId, studentId), onSuccess: (r) => (setLink(r.link), refresh()), onError: fail });
  const revoke = useMutation({ mutationFn: () => onboardingFlowApi.revokeLink(internshipId, studentId), onSuccess: () => (setLink(null), refresh()), onError: fail });
  const review = useMutation({
    mutationFn: (v: { id: string; approve: boolean }) => onboardingFlowApi.reviewDocument(internshipId, v.id, v.approve, notes[v.id]),
    onSuccess: refresh,
    onError: fail,
  });
  const info = useMutation({ mutationFn: (approve: boolean) => onboardingFlowApi.reviewInfo(internshipId, studentId, approve), onSuccess: refresh, onError: fail });
  const [refundForm, setRefundForm] = useState<Record<string, { amount: string; text: string }>>({});
  const [cancelReason, setCancelReason] = useState("");
  const [declineNote, setDeclineNote] = useState("");
  const docs = useQuery({
    queryKey: ["onboarding-flow", internshipId, "financial"],
    queryFn: () => onboardingFlowApi.financialDocuments(internshipId),
    enabled: !!detail.data?.payments,
    retry: false,
  });
  const act = useMutation({ mutationFn: (action: () => Promise<unknown>) => action(), onSuccess: () => (setError(null), refresh()), onError: fail });
  // Download: a short-lived signed link that saves the file. Viewing is separate (the in-page viewer below).
  const download = async (id: string) => {
    try {
      window.open(await onboardingFlowApi.previewDocument(internshipId, id), "_blank", "noopener,noreferrer");
    } catch (e) {
      fail(e);
    }
  };
  const [viewing, setViewing] = useState<string | null>(null);

  const d = detail.data;
  const viewed = d?.documents.find((x) => x.id === viewing);
  const reviewControls = (doc: NonNullable<typeof d>["documents"][number]) =>
    (doc.status === "submitted" || doc.status === "verified") && (
      <div className="mt-2 flex flex-wrap gap-2">
        <Input
          className="max-w-sm"
          placeholder="What needs to change (required to ask again)"
          aria-label={`What needs to change in ${doc.key} version ${doc.version}`}
          value={notes[doc.id] ?? ""}
          onChange={(e) => setNotes({ ...notes, [doc.id]: e.target.value })}
        />
        {doc.status === "submitted" && (
          <Button size="sm" disabled={review.isPending} onClick={() => review.mutate({ id: doc.id, approve: true })}>
            Verify
          </Button>
        )}
        <Button size="sm" variant="outline" disabled={!notes[doc.id]?.trim() || review.isPending} onClick={() => review.mutate({ id: doc.id, approve: false })}>
          Ask for a new one
        </Button>
      </div>
    );
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>{d?.student.name ?? "Student"}</DialogTitle>
          <DialogDescription>
            {d ? `${d.reference} · ${d.student.email} · deadline ${inZone(d.deadline, timezone)}` : "Loading…"}
          </DialogDescription>
        </DialogHeader>
        {error && <p className="text-sm text-destructive">{error}</p>}
        {d && (
          <div className="space-y-5 text-sm">
            <div className="flex flex-wrap gap-2">
              {Object.entries(d.statuses).map(([k, v]) => (
                <Badge key={k} variant={statusTone(v)}>
                  {k}: {statusLabel(v)}
                </Badge>
              ))}
            </div>

            <p className="text-xs text-muted-foreground">
              Mobile on the record: {d.student.phone ?? "none"}
              {d.payment_phone ? ` · confirmed by the student for payments: ${d.payment_phone}` : ""}
              {d.info_review_status === "pending" && (d.info_proposed.phone_change || d.info_proposed.phone) ? " (the record change is waiting for review below)" : ""}
            </p>

            {canManage && (
              <section className="space-y-2">
                <h3 className="font-semibold">Personal link</h3>
                <p className="text-muted-foreground">
                  {d.link_active ? `Active since ${inZone(d.link_issued_at, timezone)}.` : "No active link."} A new link replaces the old one.
                  {d.link_expires_at
                    ? ` The student's link ${new Date(d.link_expires_at) > new Date() ? "stops working at" : "stopped working at"} ${inZone(d.link_expires_at, timezone)} (one hour after onboarding was completed). A new link gets its own hour.`
                    : ""}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => newLink.mutate()} disabled={newLink.isPending}>
                    <Copy className="h-4 w-4" />
                    New link to copy
                  </Button>
                  {d.link_active && (
                    <Button size="sm" variant="outline" onClick={() => revoke.mutate()} disabled={revoke.isPending}>
                      <Link2Off className="h-4 w-4" />
                      Revoke link
                    </Button>
                  )}
                </div>
                {link && (
                  <div className="flex gap-2">
                    <Input readOnly value={link} aria-label="Personal onboarding link" onFocus={(e) => e.target.select()} />
                    <Button size="sm" onClick={() => void navigator.clipboard?.writeText(link)}>
                      Copy
                    </Button>
                  </div>
                )}
              </section>
            )}

            {d.info_review_status === "pending" && (
              <section className="space-y-2 rounded-md border border-amber-300 p-3">
                <h3 className="font-semibold">Proposed corrections</h3>
                <pre className="whitespace-pre-wrap text-xs">
                  {JSON.stringify(
                    { ...d.info_proposed, phone_change: undefined, phone: d.info_proposed.phone_change ? d.payment_phone : d.info_proposed.phone },
                    null,
                    2,
                  )}
                </pre>
                {canManage && (
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => info.mutate(true)}>
                      Apply
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => info.mutate(false)}>
                      Turn down
                    </Button>
                  </div>
                )}
              </section>
            )}

            <section className="space-y-2">
              <h3 className="font-semibold">Documents</h3>
              {d.documents.length === 0 && <p className="text-muted-foreground">Nothing uploaded yet.</p>}
              {d.documents.map((doc) => (
                <div key={doc.id} className={`rounded-md border p-2 ${doc.status === "superseded" ? "opacity-60" : ""}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{doc.key}</span>
                    <span className="text-muted-foreground">v{doc.version} · {doc.filename}</span>
                    <Badge variant={statusTone(doc.status)}>{statusLabel(doc.status)}</Badge>
                    {doc.sensitive && <Badge variant="outline">sensitive</Badge>}
                    <Badge variant="outline">{doc.scan_status === "clean" ? "virus scan: clean" : "not virus-scanned"}</Badge>
                    {doc.removed_at && <Badge variant="secondary">file removed</Badge>}
                    <Button size="sm" variant="ghost" disabled={!!doc.removed_at} onClick={() => setViewing(doc.id)} aria-label={`Preview ${doc.key} version ${doc.version}`}>
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button size="sm" variant="ghost" disabled={!!doc.removed_at} onClick={() => void download(doc.id)} aria-label={`Download ${doc.key} version ${doc.version}`}>
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>
                  {doc.review_note && <p className="mt-1 text-xs text-muted-foreground">Note: {doc.review_note}</p>}
                  {doc.removed_at ? (
                    <p className="mt-1 text-xs text-muted-foreground">File removed {new Date(doc.removed_at).toLocaleDateString()} after its retention period.</p>
                  ) : doc.keep_until && (
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>Retention period ends {new Date(doc.keep_until).toLocaleDateString()} (not deleted automatically).</span>
                      {new Date(doc.keep_until) <= new Date() && (
                        <Button size="sm" variant="outline" onClick={() => act.mutate(() => onboardingFlowApi.removeIdentityFile(internshipId, doc.id))}>
                          Remove file
                        </Button>
                      )}
                    </div>
                  )}
                  {reviewControls(doc)}
                </div>
              ))}
            </section>

            <section className="space-y-1">
              <h3 className="font-semibold">Acceptance</h3>
              {d.acceptance.accepted_at ? (
                <p>
                  Accepted {inZone(d.acceptance.accepted_at, timezone)} (terms v{d.acceptance.terms_version}
                  {d.acceptance.fee_snapshot ? `, fee ${money(d.acceptance.fee_snapshot.total)}` : ""}).
                </p>
              ) : d.acceptance.declined_at ? (
                <p>Declined {inZone(d.acceptance.declined_at, timezone)}{d.acceptance.decline_reason ? `: ${d.acceptance.decline_reason}` : ""}.</p>
              ) : (
                <p className="text-muted-foreground">No decision yet.</p>
              )}
              {d.acceptance.refund_terms && (
                <p className="text-xs text-muted-foreground">
                  {d.acceptance.refund_terms.allow_refund_requests
                    ? `Refund requests offered under refund policy v${d.acceptance.refund_terms.policy_version}${d.acceptance.refund_terms.request_days ? `, within ${d.acceptance.refund_terms.request_days} days of payment` : ""}.`
                    : "Refund requests were not offered (payment-terms notice shown)."}
                </p>
              )}
            </section>

            {d.refund_request && (
              <section className="space-y-2">
                <h3 className="font-semibold">Refund request</h3>
                <p>
                  {inZone(d.refund_request.requested_at, timezone)}: {d.refund_request.reason}{" "}
                  <Badge variant={d.refund_request.status === "open" ? "destructive" : "secondary"}>
                    {d.refund_request.status === "open" ? "waiting for finance" : d.refund_request.status === "declined" ? "declined" : "refund started"}
                  </Badge>
                </p>
                {d.refund_request.note && <p className="text-xs text-muted-foreground">Answer: {d.refund_request.note}</p>}
                {d.refund_request.status === "open" && d.payments && (
                  <div className="flex flex-wrap gap-2">
                    <Input className="max-w-sm" aria-label="Reason for declining the refund request" placeholder="Reason for declining (shown to the student)"
                      value={declineNote} onChange={(e) => setDeclineNote(e.target.value)} />
                    <Button size="sm" variant="outline" disabled={!declineNote.trim()}
                      onClick={() => act.mutate(() => onboardingFlowApi.declineRefundRequest(internshipId, studentId, declineNote))}>
                      Decline request
                    </Button>
                    <span className="text-xs text-muted-foreground">To agree, refund the payment in the ledger below.</span>
                  </div>
                )}
              </section>
            )}

            {d.payments && (
              <section className="space-y-2">
                <h3 className="font-semibold">Ledger</h3>
                {d.payments.length === 0 && <p className="text-muted-foreground">No entries.</p>}
                {d.payments.map((p) => (
                  <div key={p.id} className="space-y-1 rounded-md border p-2">
                    <div className="flex flex-wrap gap-2">
                      <span className="font-medium">{p.kind}</span>
                      <span>{money(p.amount, p.currency)}</span>
                      <Badge variant={statusTone(p.status)}>{statusLabel(p.status)}</Badge>
                      <span className="text-muted-foreground">{p.method ?? ""} {p.reference ?? ""} {p.note ?? ""}</span>
                    </div>
                    {p.kind === "payment" && p.status === "confirmed" && (
                      <div className="flex flex-wrap gap-2">
                        <Input className="w-28" inputMode="decimal" placeholder="Amount" value={refundForm[p.id]?.amount ?? ""} onChange={(e) => setRefundForm({ ...refundForm, [p.id]: { ...(refundForm[p.id] ?? { amount: "", text: "" }), amount: e.target.value } })} />
                        <Input className="max-w-xs" placeholder="Reason for the refund" value={refundForm[p.id]?.text ?? ""} onChange={(e) => setRefundForm({ ...refundForm, [p.id]: { ...(refundForm[p.id] ?? { amount: "", text: "" }), text: e.target.value } })} />
                        <Button size="sm" variant="outline" disabled={!refundForm[p.id]?.amount || !refundForm[p.id]?.text || act.isPending}
                          onClick={() => window.confirm(`Refund ${refundForm[p.id]?.amount} to ${d.student.name}?`) && act.mutate(() => onboardingFlowApi.refund(internshipId, p.id, refundForm[p.id].amount, refundForm[p.id].text))}>
                          Refund
                        </Button>
                      </div>
                    )}
                    {p.kind === "refund" && p.status === "awaiting_verification" && (
                      <div className="flex flex-wrap gap-2">
                        <Input className="max-w-xs" placeholder="Transfer reference, or reason to cancel" value={refundForm[p.id]?.text ?? ""} onChange={(e) => setRefundForm({ ...refundForm, [p.id]: { amount: "", text: e.target.value } })} />
                        <Button size="sm" disabled={!refundForm[p.id]?.text || act.isPending} onClick={() => act.mutate(() => onboardingFlowApi.decideRefund(internshipId, p.id, { approve: true, reference: refundForm[p.id].text }))}>
                          Money sent
                        </Button>
                        <Button size="sm" variant="outline" disabled={!refundForm[p.id]?.text || act.isPending} onClick={() => act.mutate(() => onboardingFlowApi.decideRefund(internshipId, p.id, { approve: false, note: refundForm[p.id].text }))}>
                          Cancel refund
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
                {(docs.data ?? []).filter((f) => f.application === d.reference).map((f) => (
                  <div key={f.id} className="flex flex-wrap items-center gap-2">
                    <span>{f.kind.replace("_", " ")} {f.number} · {money(f.amount, f.currency)} · email {f.email_status}</span>
                    <Button size="sm" variant="ghost" onClick={() => void onboardingFlowApi.financialUrl(internshipId, f.id).then((u) => window.open(u, "_blank", "noopener,noreferrer")).catch(fail)}>
                      Download
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => act.mutate(() => onboardingFlowApi.resendFinancial(internshipId, f.id))}>
                      Resend
                    </Button>
                  </div>
                ))}
              </section>
            )}

            {canManage && d.statuses.overall !== "cancelled" && (
              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground">Cancel this student's onboarding (withdrawal)</summary>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Input className="max-w-sm" placeholder="Reason" value={cancelReason} onChange={(e) => setCancelReason(e.target.value)} />
                  <Button size="sm" variant="destructive" disabled={!cancelReason.trim() || act.isPending}
                    onClick={() => window.confirm("Cancel this onboarding? The link stops working; refunds are made separately.") && act.mutate(() => onboardingFlowApi.cancel(internshipId, studentId, cancelReason))}>
                    Cancel onboarding
                  </Button>
                </div>
              </details>
            )}

            <section className="space-y-1">
              <h3 className="font-semibold">Timeline</h3>
              <ul className="max-h-48 space-y-0.5 overflow-y-auto text-xs">
                {d.events.map((e, i) => (
                  <li key={i}>
                    <span className="text-muted-foreground">{inZone(e.at, timezone)}</span> · {e.actor} · {e.event.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </section>
          </div>
        )}
      </DialogContent>
      {viewed && (
        <DocumentViewer internshipId={internshipId} document={viewed} onClose={() => setViewing(null)} onDownload={(id) => void download(id)}>
          {viewed.review_note && <p className="text-xs text-muted-foreground">Note: {viewed.review_note}</p>}
          {reviewControls(viewed)}
        </DocumentViewer>
      )}
    </Dialog>
  );
}
