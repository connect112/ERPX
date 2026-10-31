import { CheckCircle2, Copy, Loader2, Upload } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import { type FormFieldDef, type PortalView, portalApi } from "@/features/internship-onboarding/api";
import { inZone, money, statusLabel, statusTone, tokenFromHash } from "@/features/internship-onboarding/lib/format";

const STORE = "erpx-onboarding-token";
const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

/** The token is read from the link's fragment, kept for this tab only, and removed from the address bar. */
function useToken(): string | null {
  return useMemo(() => {
    const fromHash = tokenFromHash(window.location.hash);
    try {
      if (fromHash) sessionStorage.setItem(STORE, fromHash);
      if (window.location.hash) window.history.replaceState(null, "", window.location.pathname + window.location.search);
      return fromHash ?? sessionStorage.getItem(STORE);
    } catch {
      return fromHash;
    }
  }, []);
}

function visible(field: FormFieldDef, answers: Record<string, unknown>): boolean {
  return !field.visible_if || answers[field.visible_if.field] === field.visible_if.equals;
}

declare global {
  interface Window {
    Cashfree?: (opts: { mode: string }) => { checkout: (opts: { paymentSessionId: string; redirectTarget: string }) => Promise<unknown> };
  }
}

function loadCashfree(): Promise<void> {
  if (window.Cashfree) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://sdk.cashfree.com/js/v3/cashfree.js";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("The payment page could not be loaded."));
    document.head.appendChild(script);
  });
}

export function OnboardingPortalPage() {
  const token = useToken();
  const [view, setView] = useState<PortalView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [info, setInfo] = useState<{ name: string; phone: string }>({ name: "", phone: "" });
  const [declared, setDeclared] = useState(false);
  const [declineReason, setDeclineReason] = useState("");
  const [progress, setProgress] = useState<Record<string, number>>({});
  const [pay, setPay] = useState({ method: "", reference: "", paid_on: "", amount: "", remarks: "" });
  const [proof, setProof] = useState<File | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "referrer";
    meta.content = "no-referrer";
    document.head.appendChild(meta);
    return () => meta.remove();
  }, []);

  const apply = useCallback((v: PortalView) => {
    setView(v);
    setAnswers(v.form.answers);
    setInfo({ name: v.information.proposed.name ?? v.information.current.name, phone: v.information.proposed.phone ?? v.information.current.phone ?? "" });
    setPay((p) => ({ ...p, amount: v.payment.balance, method: p.method || v.payment.methods.find((m) => m !== "cashfree") || "" }));
  }, []);

  const run = useCallback(
    async (label: string, action: () => Promise<PortalView | void>) => {
      setBusy(label);
      setError(null);
      try {
        const v = await action();
        if (v) apply(v);
      } catch (e) {
        setError(errorMessage(e, "Something went wrong. Please try again."));
      } finally {
        setBusy(null);
      }
    },
    [apply]
  );

  useEffect(() => {
    if (!token) return;
    const returning = new URLSearchParams(window.location.search).has("order");
    void run("load", () => (returning ? portalApi.refresh(token) : portalApi.view(token)));
  }, [token, run]);

  if (!token || (error && !view)) {
    return (
      <Shell>
        <Card>
          <CardHeader>
            <CardTitle>Onboarding link not valid</CardTitle>
            <CardDescription>
              {error ?? "Open the link from your most recent onboarding email. Each new email replaces the previous link."}
            </CardDescription>
          </CardHeader>
        </Card>
      </Shell>
    );
  }
  if (!view) {
    return (
      <Shell>
        <p className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading your onboarding…
        </p>
      </Shell>
    );
  }

  const v = view;
  const accepted = v.statuses.offer === "accepted";
  const declined = v.statuses.offer === "declined";
  const editable = v.open && !accepted && !declined;
  const saveDraft = (step: string, withInfo: boolean) =>
    run("save", async () => {
      const body: Record<string, unknown> = { step, answers };
      if (withInfo && v.information.editable) body.info = { name: info.name, phone: info.phone };
      const r = await portalApi.save(token, body);
      setFieldErrors(r.errors);
      setSaved(Object.keys(r.errors).length ? null : "Saved. You can come back to this link later.");
      return portalApi.view(token);
    });

  return (
    <Shell>
      <Card>
        <CardHeader>
          <CardDescription>{v.organization}</CardDescription>
          <CardTitle className="text-xl">{v.internship.title}</CardTitle>
          <div className="space-y-1 text-sm">
            <div>
              {v.student_name} · Application <span className="font-mono">{v.reference}</span>
            </div>
            <div className="text-muted-foreground">Complete by {inZone(v.deadline, v.timezone)}</div>
            <div className="flex flex-wrap gap-1 pt-1">
              {Object.entries(v.statuses).map(([k, s]) => (
                <Badge key={k} variant={statusTone(s)}>
                  {k}: {statusLabel(s)}
                </Badge>
              ))}
            </div>
          </div>
        </CardHeader>
      </Card>

      {!v.open && !v.completion.completed && (
        <Card className="border-amber-300">
          <CardContent className="pt-6 text-sm">
            Onboarding is closed for new submissions. What you already submitted is kept.
            {v.contact.email && <> Contact <a className="underline" href={`mailto:${v.contact.email}`}>{v.contact.email}</a></>}
            {v.contact.phone && <> or call {v.contact.phone}</>} if you need more time.
          </CardContent>
        </Card>
      )}
      {error && <p className="rounded-md border border-destructive p-3 text-sm text-destructive" role="alert">{error}</p>}
      {saved && <p className="text-sm text-emerald-700 dark:text-emerald-400">{saved}</p>}

      {v.completion.completed && (
        <Card className="border-emerald-300">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" /> Congratulations, {v.student_name}!
            </CardTitle>
            <CardDescription>Your onboarding for {v.internship.title} is complete.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {v.payment.required && <p>Payment received: {money(v.payment.paid, v.payment.currency)}.</p>}
            {v.completion.next_steps && <p className="whitespace-pre-line">{v.completion.next_steps}</p>}
            <p>LMS access: {statusLabel(v.completion.lms_status)}.</p>
            {v.completion.whatsapp_link && (
              <a className="inline-block rounded-md bg-emerald-600 px-4 py-2 text-white" href={v.completion.whatsapp_link} target="_blank" rel="noopener noreferrer">
                Join the WhatsApp group
              </a>
            )}
          </CardContent>
        </Card>
      )}

      <Step title="1. Your details" done={accepted}>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted-foreground">Email</dt>
          <dd>{v.information.current.email}</dd>
          <dt className="text-muted-foreground">Institution</dt>
          <dd>{v.information.current.institution ?? "—"}</dd>
          {Object.entries(v.information.current.details).map(([k, val]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{k}</dt>
              <dd>{val}</dd>
            </div>
          ))}
        </dl>
        {v.information.editable && editable ? (
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="info-name">Full name</Label>
              <Input id="info-name" value={info.name} onChange={(e) => setInfo({ ...info, name: e.target.value })} />
            </div>
            <div className="space-y-1">
              <Label htmlFor="info-phone">Mobile number</Label>
              <Input id="info-phone" inputMode="tel" value={info.phone} onChange={(e) => setInfo({ ...info, phone: e.target.value })} />
            </div>
            <p className="text-xs text-muted-foreground sm:col-span-2">Changes are checked by the internship team before they replace your records.</p>
          </div>
        ) : (
          <p className="text-sm">
            {v.information.current.name} · {v.information.current.phone ?? "no phone"}
          </p>
        )}
        {v.information.review === "pending" && <p className="text-xs text-amber-700">Your corrections are waiting for review.</p>}
      </Step>

      {v.form.fields.length > 0 && (
        <Step title="2. A few questions" done={accepted}>
          {v.form.fields.filter((f) => visible(f, answers)).map((f) => (
            <FieldInput key={f.key} field={f} value={answers[f.key]} error={fieldErrors[f.key]} disabled={!editable || f.editable === false}
              onChange={(val) => setAnswers({ ...answers, [f.key]: val })} />
          ))}
        </Step>
      )}
      {editable && (
        <Button variant="outline" disabled={busy !== null} onClick={() => saveDraft("form", true)}>
          {busy === "save" ? "Saving…" : "Save and continue later"}
        </Button>
      )}

      {v.documents.length > 0 && (
        <Step title="3. Documents" done={v.statuses.documents === "verified"}>
          {v.documents.map((d) => (
            <div key={d.key} className="space-y-1 rounded-md border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{d.label}</span>
                {!d.required && <span className="text-xs text-muted-foreground">(optional)</span>}
                <Badge variant={statusTone(d.status)}>{statusLabel(d.status)}</Badge>
              </div>
              {d.instructions && <p className="text-xs text-muted-foreground">{d.instructions}</p>}
              {d.note && <p className="text-sm text-destructive">Please upload again: {d.note}</p>}
              {d.filename && <p className="text-xs">Uploaded: {d.filename}</p>}
              {v.open && !declined && d.status !== "verified" && (
                <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-primary">
                  <Upload className="h-4 w-4" />
                  {d.filename ? "Replace file" : "Upload file"} ({(d.types ?? []).join(", ").toUpperCase()}, up to {d.max_mb} MB)
                  <input
                    type="file"
                    className="sr-only"
                    accept={(d.types ?? []).map((t) => (t === "jpg" ? ".jpg,.jpeg" : `.${t}`)).join(",")}
                    disabled={busy !== null}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = "";
                      if (!file) return;
                      if (file.size > (d.max_mb ?? 5) * 1024 * 1024) {
                        setError(`${d.label}: the file is larger than ${d.max_mb} MB.`);
                        return;
                      }
                      void run(`doc-${d.key}`, async () => {
                        await portalApi.upload(token, d.key, file, (pct) => setProgress((p) => ({ ...p, [d.key]: pct })));
                        return portalApi.view(token);
                      });
                    }}
                  />
                </label>
              )}
              {busy === `doc-${d.key}` && <p className="text-xs text-muted-foreground">Uploading… {progress[d.key] ?? 0}%</p>}
            </div>
          ))}
        </Step>
      )}

      <Step title="4. Accept your offer" done={accepted}>
        {v.acceptance.fees && v.payment.required && (
          <table className="w-full text-sm">
            <tbody>
              <tr><td>{v.acceptance.fees.description}</td><td className="text-right">{money(v.acceptance.fees.base, v.acceptance.fees.currency)}</td></tr>
              {v.acceptance.fees.discount !== "0.00" && <tr><td>Discount</td><td className="text-right">-{money(v.acceptance.fees.discount)}</td></tr>}
              {v.acceptance.fees.tax_mode !== "none" && (
                <tr><td>{v.acceptance.fees.tax_label} ({v.acceptance.fees.tax_rate_percent}%{v.acceptance.fees.tax_mode === "inclusive" ? ", included" : ""})</td><td className="text-right">{money(v.acceptance.fees.tax)}</td></tr>
              )}
              <tr className="font-semibold"><td>Total payable</td><td className="text-right">{money(v.payment.payable, v.payment.currency)}</td></tr>
            </tbody>
          </table>
        )}
        {accepted ? (
          <p className="text-sm">You accepted the offer on {inZone(v.acceptance.accepted_at, v.timezone)}.</p>
        ) : declined ? (
          <p className="text-sm">You declined this offer. Contact the internship team if this was a mistake.</p>
        ) : (
          <>
            <p className="whitespace-pre-line rounded-md bg-muted p-3 text-sm">{v.acceptance.declaration}</p>
            {v.acceptance.terms_url && (
              <a className="text-sm underline" href={v.acceptance.terms_url} target="_blank" rel="noopener noreferrer">Read the full terms</a>
            )}
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1" checked={declared} disabled={!editable} onChange={(e) => setDeclared(e.target.checked)} />I have read and agree to the declaration above.
            </label>
            <div className="flex flex-wrap gap-2">
              <Button disabled={!declared || !editable || busy !== null} onClick={() => void run("accept", async () => {
                await portalApi.save(token, { answers, step: "acceptance" });
                return portalApi.accept(token, v.acceptance.terms_version);
              })}>
                {busy === "accept" ? "Accepting…" : "Accept the offer"}
              </Button>
            </div>
            <details className="text-sm">
              <summary className="cursor-pointer text-muted-foreground">Decline the offer</summary>
              <div className="mt-2 space-y-2">
                <Textarea placeholder="Reason (optional)" value={declineReason} onChange={(e) => setDeclineReason(e.target.value)} />
                <Button variant="outline" disabled={!editable || busy !== null} onClick={() => window.confirm("Decline this internship offer? This cannot be undone here.") && void run("decline", () => portalApi.decline(token, declineReason))}>
                  Decline
                </Button>
              </div>
            </details>
          </>
        )}
      </Step>

      {v.financial_documents.length > 0 && (
        <Step title="Receipts" done>
          <ul className="space-y-1 text-sm">
            {v.financial_documents.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {d.kind === "credit_note" ? "Credit note" : d.kind === "tax_invoice" ? "Tax invoice" : "Receipt"} {d.number} ·{" "}
                  {money(d.amount, d.currency)}
                </span>
                <Button size="sm" variant="outline" onClick={() => void run("receipt", async () => {
                  window.open(await portalApi.financialUrl(token, d.id), "_blank", "noopener,noreferrer");
                })}>
                  Download
                </Button>
              </li>
            ))}
          </ul>
        </Step>
      )}

      {v.payment.required && accepted && (
        <Step title="5. Payment" done={v.statuses.payment === "paid"}>
          <p className="text-sm">
            Paid {money(v.payment.paid, v.payment.currency)} of {money(v.payment.payable, v.payment.currency)} · balance{" "}
            <strong>{money(v.payment.balance, v.payment.currency)}</strong>
            {v.payment.deadline && <> · pay by {inZone(v.payment.deadline, v.timezone)}</>}
          </p>
          {v.statuses.payment === "awaiting_manual_verification" && (
            <p className="text-sm text-amber-700">We received your payment details and are checking them with the bank. You will get an email once it is confirmed.</p>
          )}
          {!v.payment.open && v.statuses.payment !== "paid" && v.statuses.payment !== "awaiting_manual_verification" && (
            <p className="text-sm text-muted-foreground">Payment opens once your documents are {v.statuses.documents === "verified" ? "checked" : "submitted and checked"}.</p>
          )}
          {v.payment.open && (
            <div className="space-y-3">
              {v.payment.methods.includes("cashfree") && (
                <div className="space-y-2 rounded-md border p-3">
                  <div className="font-medium">Pay online</div>
                  <Button disabled={busy !== null} onClick={() => void run("checkout", async () => {
                    const session = await portalApi.checkout(token);
                    await loadCashfree();
                    await window.Cashfree!({ mode: session.environment }).checkout({ paymentSessionId: session.payment_session_id, redirectTarget: "_self" });
                  })}>
                    {busy === "checkout" ? "Opening the payment page…" : `Pay ${money(v.payment.balance, v.payment.currency)} online`}
                  </Button>
                  <Button variant="ghost" size="sm" disabled={busy !== null} onClick={() => void run("refresh", () => portalApi.refresh(token))}>
                    I have paid: check status
                  </Button>
                </div>
              )}
              {(v.payment.bank || v.payment.upi) && (
                <div className="space-y-2 rounded-md border p-3 text-sm">
                  <div className="font-medium">Pay by bank transfer or UPI</div>
                  {v.payment.bank && (
                    <dl className="grid grid-cols-[auto_1fr] gap-x-3">
                      <dt className="text-muted-foreground">Account name</dt><dd>{v.payment.bank.holder}</dd>
                      <dt className="text-muted-foreground">Bank</dt><dd>{v.payment.bank.bank} {v.payment.bank.branch}</dd>
                      <dt className="text-muted-foreground">Account number</dt><dd className="font-mono">{v.payment.bank.account_number} <CopyButton text={v.payment.bank.account_number} /></dd>
                      <dt className="text-muted-foreground">IFSC</dt><dd className="font-mono">{v.payment.bank.ifsc} <CopyButton text={v.payment.bank.ifsc} /></dd>
                    </dl>
                  )}
                  {v.payment.upi && (
                    <p>UPI ID: <span className="font-mono">{v.payment.upi.vpa}</span> <CopyButton text={v.payment.upi.vpa} /> ({v.payment.upi.beneficiary})</p>
                  )}
                  {(v.payment.bank?.instructions || v.payment.upi?.instructions) && <p className="text-muted-foreground">{v.payment.bank?.instructions} {v.payment.upi?.instructions}</p>}
                  <div className="grid gap-2 sm:grid-cols-2">
                    <select aria-label="How you paid" className={selectClass} value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value })}>
                      {v.payment.bank && <option value="bank_transfer">Bank transfer</option>}
                      {v.payment.upi && <option value="upi">UPI</option>}
                    </select>
                    <Input aria-label="Transaction reference (UTR)" placeholder="Transaction reference (UTR)" value={pay.reference} onChange={(e) => setPay({ ...pay, reference: e.target.value })} />
                    <Input aria-label="Payment date" type="date" value={pay.paid_on} onChange={(e) => setPay({ ...pay, paid_on: e.target.value })} />
                    <Input aria-label="Amount paid" inputMode="decimal" value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} />
                    <Input aria-label="Receipt or screenshot" type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setProof(e.target.files?.[0] ?? null)} />
                    <Input aria-label="Remarks" placeholder="Remarks (optional)" value={pay.remarks} onChange={(e) => setPay({ ...pay, remarks: e.target.value })} />
                  </div>
                  <Button disabled={busy !== null || !pay.method || !pay.reference || !pay.paid_on || !proof} onClick={() => void run("manual", () => portalApi.manualPayment(token, { ...pay, remarks: pay.remarks || undefined }, proof!))}>
                    {busy === "manual" ? "Submitting…" : "Submit payment details"}
                  </Button>
                </div>
              )}
            </div>
          )}
        </Step>
      )}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto w-full max-w-2xl space-y-4 px-4 py-6 sm:py-10">{children}</main>;
}

function Step({ title, done, children }: { title: string; done: boolean; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          {done && <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-label="done" />}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}

function CopyButton({ text }: { text: string }) {
  return (
    <button type="button" aria-label="Copy" className="inline-flex align-middle text-muted-foreground hover:text-foreground" onClick={() => void navigator.clipboard?.writeText(text)}>
      <Copy className="h-3.5 w-3.5" />
    </button>
  );
}

function FieldInput({ field, value, error, disabled, onChange }: { field: FormFieldDef; value: unknown; error?: string; disabled: boolean; onChange: (v: unknown) => void }) {
  const id = `f-${field.key}`;
  const label = (
    <Label htmlFor={id}>
      {field.label}
      {field.required && <span className="text-destructive"> *</span>}
    </Label>
  );
  let control: React.ReactNode;
  switch (field.type) {
    case "long_text":
      control = <Textarea id={id} disabled={disabled} placeholder={field.placeholder} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
      break;
    case "dropdown":
      control = (
        <select id={id} className={selectClass} disabled={disabled} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
          <option value="">Choose…</option>
          {(field.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      );
      break;
    case "radio":
      control = (
        <div role="radiogroup" aria-labelledby={id} className="flex flex-wrap gap-3">
          {(field.options ?? []).map((o) => (
            <label key={o} className="flex items-center gap-1 text-sm">
              <input type="radio" name={id} disabled={disabled} checked={value === o} onChange={() => onChange(o)} /> {o}
            </label>
          ))}
        </div>
      );
      break;
    case "multi_select": {
      const list = Array.isArray(value) ? (value as string[]) : [];
      control = (
        <div className="flex flex-wrap gap-3">
          {(field.options ?? []).map((o) => (
            <label key={o} className="flex items-center gap-1 text-sm">
              <input type="checkbox" disabled={disabled} checked={list.includes(o)} onChange={(e) => onChange(e.target.checked ? [...list, o] : list.filter((x) => x !== o))} /> {o}
            </label>
          ))}
        </div>
      );
      break;
    }
    case "checkbox":
    case "declaration":
      return (
        <div className="space-y-1">
          <label className="flex items-start gap-2 text-sm">
            <input id={id} type="checkbox" className="mt-1" disabled={disabled} checked={value === true} onChange={(e) => onChange(e.target.checked)} />
            <span>{field.label}{field.required && <span className="text-destructive"> *</span>}</span>
          </label>
          {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
      );
    default:
      control = (
        <Input id={id} disabled={disabled} placeholder={field.placeholder}
          type={field.type === "email" ? "email" : field.type === "date" ? "date" : "text"}
          inputMode={field.type === "number" ? "decimal" : field.type === "phone" ? "tel" : undefined}
          value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />
      );
  }
  return (
    <div className="space-y-1">
      {label}
      {field.description && <p className="text-xs text-muted-foreground">{field.description}</p>}
      {control}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
