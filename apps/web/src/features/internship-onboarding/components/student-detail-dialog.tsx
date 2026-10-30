import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Eye, Link2Off } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/features/institutions/lib/format";
import { onboardingFlowApi } from "@/features/internship-onboarding/api";
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
  const preview = async (id: string) => {
    try {
      window.open(await onboardingFlowApi.previewDocument(internshipId, id), "_blank", "noopener,noreferrer");
    } catch (e) {
      fail(e);
    }
  };

  const d = detail.data;
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

            {canManage && (
              <section className="space-y-2">
                <h3 className="font-semibold">Personal link</h3>
                <p className="text-muted-foreground">
                  {d.link_active ? `Active since ${inZone(d.link_issued_at, timezone)}.` : "No active link."} A new link replaces the old one.
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
                <pre className="whitespace-pre-wrap text-xs">{JSON.stringify(d.info_proposed, null, 2)}</pre>
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
                    <Button size="sm" variant="ghost" onClick={() => void preview(doc.id)} aria-label={`Preview ${doc.key} version ${doc.version}`}>
                      <Eye className="h-4 w-4" />
                    </Button>
                  </div>
                  {doc.review_note && <p className="mt-1 text-xs text-muted-foreground">Note: {doc.review_note}</p>}
                  {(doc.status === "submitted" || doc.status === "verified") && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Input
                        className="max-w-sm"
                        placeholder="What needs to change (required to ask again)"
                        value={notes[doc.id] ?? ""}
                        onChange={(e) => setNotes({ ...notes, [doc.id]: e.target.value })}
                      />
                      {doc.status === "submitted" && (
                        <Button size="sm" onClick={() => review.mutate({ id: doc.id, approve: true })}>
                          Verify
                        </Button>
                      )}
                      <Button size="sm" variant="outline" disabled={!notes[doc.id]?.trim()} onClick={() => review.mutate({ id: doc.id, approve: false })}>
                        Ask for a new one
                      </Button>
                    </div>
                  )}
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
            </section>

            {d.payments && (
              <section className="space-y-1">
                <h3 className="font-semibold">Ledger</h3>
                {d.payments.length === 0 && <p className="text-muted-foreground">No entries.</p>}
                {d.payments.map((p) => (
                  <div key={p.id} className="flex flex-wrap gap-2">
                    <span>{p.kind}</span>
                    <span>{money(p.amount, p.currency)}</span>
                    <Badge variant={statusTone(p.status)}>{statusLabel(p.status)}</Badge>
                    <span className="text-muted-foreground">{p.method ?? ""} {p.reference ?? ""} {p.note ?? ""}</span>
                  </div>
                ))}
              </section>
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
    </Dialog>
  );
}
