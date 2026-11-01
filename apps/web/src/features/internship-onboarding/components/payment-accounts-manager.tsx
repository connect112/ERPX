import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/features/institutions/lib/format";
import { type SavedAccount, paymentAccountsApi } from "@/features/internship-onboarding/api";

const FIELDS = {
  bank: [["holder", "Account holder"], ["bank", "Bank name"], ["account_number", "Account number"], ["ifsc", "IFSC"], ["branch", "Branch (optional)"], ["instructions", "Payment instructions"]],
  upi: [["vpa", "UPI ID (name@bank)"], ["beneficiary", "Payee name"], ["instructions", "Payment instructions"]],
} as const;

type Kind = keyof typeof FIELDS;
const blank = (kind: Kind) => Object.fromEntries(FIELDS[kind].map(([k]) => [k, ""])) as Record<string, string>;

/** The organization's saved bank/UPI accounts (finance only). Students see one only once it is verified and switched on. */
export function PaymentAccountsManager() {
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: ["onboarding-payment-accounts"], queryFn: paymentAccountsApi.list });
  const [draft, setDraft] = useState<{ id?: string; kind: Kind; label: string; details: Record<string, string> } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const act = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => {
      setError(null);
      setDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["onboarding-payment-accounts"] });
    },
    onError: (e) => setError(errorMessage(e, "That did not work.")),
  });

  const edit = (a: SavedAccount) =>
    setDraft({ id: a.id, kind: a.kind, label: a.label, details: Object.fromEntries(FIELDS[a.kind].map(([k]) => [k, String(a.details[k] ?? "")])) });
  const save = () => {
    if (!draft) return;
    const details = draft.kind === "upi" ? { ...draft.details, show_qr: true } : draft.details;
    act.mutate(() => (draft.id ? paymentAccountsApi.update(draft.id, { label: draft.label, details }) : paymentAccountsApi.create({ kind: draft.kind, label: draft.label, details })));
  };

  return (
    <div className="space-y-3 text-sm">
      <p className="text-muted-foreground">
        Accounts students pay into, reusable across internships. A new or edited account is shown to students only after a finance user marks it
        verified (check it against the bank's letter or the UPI app). Every change is logged.
      </p>
      {error && <p className="text-destructive">{error}</p>}
      {list.isError && <p className="text-destructive">{errorMessage(list.error, "Only finance staff can see payment accounts.")}</p>}
      {(list.data ?? []).length === 0 && list.isSuccess && <p className="text-muted-foreground">No saved accounts yet.</p>}
      {(list.data ?? []).map((a) => (
        <div key={a.id} className={`space-y-1 rounded-md border p-2 ${a.enabled ? "" : "opacity-60"}`}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{a.label}</span>
            <Badge variant="outline">{a.kind === "bank" ? "Bank" : "UPI"}</Badge>
            <Badge variant={a.verified ? "secondary" : "destructive"}>{a.verified ? "verified" : "not verified"}</Badge>
            {!a.enabled && <Badge variant="outline">switched off</Badge>}
          </div>
          <p className="font-mono text-xs text-muted-foreground">
            {a.kind === "bank" ? `${a.details.holder} · ${a.details.bank} · ${a.details.account_number} · ${a.details.ifsc}` : `${a.details.vpa} · ${a.details.beneficiary}`}
          </p>
          <div className="flex flex-wrap gap-2">
            {!a.verified && <Button size="sm" onClick={() => act.mutate(() => paymentAccountsApi.verify(a.id))}>Mark verified</Button>}
            <Button size="sm" variant="outline" onClick={() => edit(a)}>Edit</Button>
            <Button size="sm" variant="ghost" onClick={() => act.mutate(() => paymentAccountsApi.update(a.id, { enabled: !a.enabled }))}>
              {a.enabled ? "Switch off" : "Switch on"}
            </Button>
          </div>
        </div>
      ))}
      {draft ? (
        <div className="space-y-2 rounded-md border p-2">
          <div className="font-medium">{draft.id ? "Edit account (it will need verifying again)" : `New ${draft.kind === "bank" ? "bank account" : "UPI ID"}`}</div>
          <Input aria-label="Account name in ERPX" placeholder="Name staff will recognise" value={draft.label} onChange={(e) => setDraft({ ...draft, label: e.target.value })} />
          <div className="grid gap-2 sm:grid-cols-3">
            {FIELDS[draft.kind].map(([k, label]) => (
              <Input key={k} aria-label={label} placeholder={label} value={draft.details[k] ?? ""}
                onChange={(e) => setDraft({ ...draft, details: { ...draft.details, [k]: k === "ifsc" ? e.target.value.toUpperCase() : e.target.value } })} />
            ))}
          </div>
          <div className="flex gap-2">
            <Button size="sm" disabled={!draft.label.trim() || act.isPending} onClick={save}>Save</Button>
            <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => setDraft({ kind: "bank", label: "", details: blank("bank") })}>Add bank account</Button>
          <Button size="sm" variant="outline" onClick={() => setDraft({ kind: "upi", label: "", details: blank("upi") })}>Add UPI ID</Button>
        </div>
      )}
    </div>
  );
}
