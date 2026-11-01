import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { errorMessage } from "@/features/institutions/lib/format";
import { onboardingFlowApi } from "@/features/internship-onboarding/api";
import { money, statusLabel, statusTone } from "@/features/internship-onboarding/lib/format";

/** Bank/UPI claims waiting for a finance check, one at a time: a screenshot is not money, the account statement is. */
export function PaymentsQueue({ internshipId }: { internshipId: string }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("awaiting_verification");
  const [form, setForm] = useState<Record<string, { amount: string; note: string }>>({});
  const [error, setError] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["onboarding-flow", internshipId, "payments", status], queryFn: () => onboardingFlowApi.payments(internshipId, status) });
  const verify = useMutation({
    mutationFn: (v: { id: string; approve: boolean }) =>
      onboardingFlowApi.verifyPayment(internshipId, v.id, {
        approve: v.approve,
        amount_received: form[v.id]?.amount || undefined,
        note: form[v.id]?.note || undefined,
      }),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["onboarding-flow", internshipId] });
    },
    onError: (e) => setError(errorMessage(e, "Could not save the decision.")),
  });
  const proof = async (id: string) => {
    try {
      window.open(await onboardingFlowApi.proof(internshipId, id), "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(errorMessage(e, "Could not open the proof."));
    }
  };
  const edit = (id: string, patch: Partial<{ amount: string; note: string }>) =>
    setForm({ ...form, [id]: { ...(form[id] ?? { amount: "", note: "" }), ...patch } });

  if (list.isError) return <p className="text-sm text-destructive">{errorMessage(list.error, "Payments need the finance permission.")}</p>;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select aria-label="Payment status" className="rounded-md border bg-background px-3 py-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="awaiting_verification">Waiting for verification</option>
          <option value="confirmed">Confirmed</option>
          <option value="rejected">Rejected</option>
          <option value="failed">Failed (online)</option>
          <option value="">Everything</option>
        </select>
        <p className="text-xs text-muted-foreground">Confirm only after the money shows in the bank account. Rejecting needs a reason.</p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Application</TableHead>
              <TableHead>Method / UTR</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Paid on</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Decision</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(list.data ?? []).map((p) => (
              <TableRow key={p.id}>
                <TableCell>{p.reference_number}</TableCell>
                <TableCell>
                  <div>{p.method}</div>
                  <div className="font-mono text-xs">{p.transaction_reference}</div>
                  {p.same_proof_used_elsewhere && <Badge variant="destructive">same proof used elsewhere</Badge>}
                </TableCell>
                <TableCell>{money(p.amount, p.currency)}</TableCell>
                <TableCell>{p.paid_on ?? "—"}</TableCell>
                <TableCell>
                  <Badge variant={statusTone(p.status)}>{statusLabel(p.status)}</Badge>
                  {p.rejection_reason && <div className="text-xs text-muted-foreground">{p.rejection_reason}</div>}
                </TableCell>
                <TableCell className="min-w-[260px]">
                  {p.has_proof && (
                    <Button size="sm" variant="ghost" onClick={() => void proof(p.id)} aria-label="Open the payment proof">
                      <Eye className="h-4 w-4" />
                    </Button>
                  )}
                  {p.status === "awaiting_verification" && (
                    <div className="mt-1 space-y-1">
                      <Input placeholder={`Amount received (default ${p.amount})`} inputMode="decimal" value={form[p.id]?.amount ?? ""} onChange={(e) => edit(p.id, { amount: e.target.value })} />
                      <Input placeholder="Note / reason" value={form[p.id]?.note ?? ""} onChange={(e) => edit(p.id, { note: e.target.value })} />
                      <div className="flex gap-2">
                        <Button size="sm" disabled={verify.isPending} onClick={() => verify.mutate({ id: p.id, approve: true })}>
                          Money received
                        </Button>
                        <Button size="sm" variant="outline" disabled={verify.isPending || !form[p.id]?.note?.trim()} onClick={() => verify.mutate({ id: p.id, approve: false })}>
                          Reject
                        </Button>
                      </div>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {!list.isLoading && (list.data ?? []).length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                  Nothing here.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
