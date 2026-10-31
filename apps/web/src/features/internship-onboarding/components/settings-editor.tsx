import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import {
  type ConfigView,
  type DocumentDef,
  type FieldType,
  type FormFieldDef,
  type OnboardingSettings,
  type PaymentMethod,
  onboardingFlowApi,
} from "@/features/internship-onboarding/api";
import { fromLocalInput, money, slugKey, toLocalInput } from "@/features/internship-onboarding/lib/format";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";
const FIELD_TYPES: [FieldType, string][] = [
  ["short_text", "Short text"], ["long_text", "Long text"], ["email", "Email"], ["phone", "Phone"], ["number", "Number"],
  ["date", "Date"], ["dropdown", "Dropdown"], ["radio", "Radio buttons"], ["checkbox", "Checkbox"],
  ["multi_select", "Multiple choice"], ["declaration", "Declaration (must be ticked)"],
];  // prettier-ignore
const CHOICE: FieldType[] = ["dropdown", "radio", "multi_select"];

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-3 rounded-md border p-4">
      <legend className="px-1 text-sm font-semibold">{title}</legend>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {children}
    </fieldset>
  );
}

function Check({ label, checked, onChange, disabled }: { label: string; checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

function move<T>(list: T[], i: number, by: number): T[] {
  const j = i + by;
  if (j < 0 || j >= list.length) return list;
  const next = [...list];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

export function SettingsEditor({ internshipId, view }: { internshipId: string; view: ConfigView }) {
  const queryClient = useQueryClient();
  const [s, setS] = useState<OnboardingSettings>(view.settings);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [templateName, setTemplateName] = useState("");
  useEffect(() => setS(view.settings), [view]);
  const finance = view.can_edit_finance;
  const templates = useQuery({ queryKey: ["onboarding-templates"], queryFn: onboardingFlowApi.templates });

  const after = (text: string) => {
    setNotice({ ok: true, text });
    void queryClient.invalidateQueries({ queryKey: ["onboarding-flow", internshipId] });
  };
  const fail = (e: unknown) => setNotice({ ok: false, text: errorMessage(e, "The settings could not be saved.") });
  const save = useMutation({ mutationFn: () => onboardingFlowApi.saveConfig(internshipId, s), onSuccess: (v) => after(`Saved as version ${v.version}.`), onError: fail });
  const apply = useMutation({
    mutationFn: (id: string) => onboardingFlowApi.applyTemplate(internshipId, id),
    onSuccess: () => after("Template applied. Students who already accepted keep their accepted terms."),
    onError: fail,
  });
  const asTemplate = useMutation({
    mutationFn: () => onboardingFlowApi.saveAsTemplate(templateName, internshipId),
    onSuccess: () => {
      setTemplateName("");
      after("Saved as a template (from the last saved settings).");
      void queryClient.invalidateQueries({ queryKey: ["onboarding-templates"] });
    },
    onError: fail,
  });

  const set = <K extends keyof OnboardingSettings>(key: K, value: Partial<OnboardingSettings[K]>) =>
    setS((cur) => ({ ...cur, [key]: { ...(cur[key] as object), ...value } }));
  const setDoc = (i: number, patch: Partial<DocumentDef>) => setS((cur) => ({ ...cur, documents: cur.documents.map((d, j) => (j === i ? { ...d, ...patch } : d)) }));
  const setField = (i: number, patch: Partial<FormFieldDef>) => setS((cur) => ({ ...cur, form: cur.form.map((f, j) => (j === i ? { ...f, ...patch } : f)) }));
  const toggleMethod = (m: PaymentMethod, on: boolean) =>
    set("fees", { methods: on ? [...new Set([...s.fees.methods, m])] : s.fees.methods.filter((x) => x !== m) });
  const dt = (name: keyof OnboardingSettings["deadlines"], label: string) => (
    <div className="space-y-1.5">
      <Label htmlFor={`dl-${name}`}>{label}</Label>
      <Input
        id={`dl-${name}`}
        type="datetime-local"
        value={toLocalInput(s.deadlines[name] as string | null)}
        onChange={(e) => set("deadlines", { [name]: fromLocalInput(e.target.value) })}
      />
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2 rounded-md bg-muted/40 p-3 text-sm">
        <span className="text-muted-foreground">
          Version {view.version}
          {view.template_id ? ` · from template v${view.template_version}` : ""}
        </span>
        <select aria-label="Apply a template" className="rounded-md border bg-background px-3 py-2 text-sm" value="" onChange={(e) => e.target.value && apply.mutate(e.target.value)}>
          <option value="">Apply a template…</option>
          {(templates.data ?? []).map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} (v{t.version})
            </option>
          ))}
        </select>
        <Input className="max-w-[220px]" placeholder="New template name" value={templateName} onChange={(e) => setTemplateName(e.target.value)} />
        <Button size="sm" variant="outline" disabled={!templateName.trim() || asTemplate.isPending} onClick={() => asTemplate.mutate()}>
          Save as template
        </Button>
      </div>

      <Section title="How students onboard" hint="Manual keeps the existing staff-only process. Automated and hybrid send each student a personal link.">
        <select aria-label="Onboarding mode" className={selectClass} value={s.modes.mode} onChange={(e) => set("modes", { mode: e.target.value as OnboardingSettings["modes"]["mode"] })}>
          <option value="manual">Manual (staff record everything)</option>
          <option value="automated">Automated (students use their link)</option>
          <option value="hybrid">Hybrid (students use their link; staff can step in)</option>
        </select>
        <div className="grid gap-2 sm:grid-cols-2">
          <Check label="Students may correct their details (reviewed by staff)" checked={s.modes.allow_info_edit} onChange={(v) => set("modes", { allow_info_edit: v })} />
          <Check label="Documents must be verified" checked={s.modes.require_documents} onChange={(v) => set("modes", { require_documents: v })} />
          <Check label="Payment is required" checked={s.modes.require_payment} disabled={!finance} onChange={(v) => set("modes", { require_payment: v })} />
          <Check label="Allow individual late onboarding" checked={s.modes.allow_late_onboarding} onChange={(v) => set("modes", { allow_late_onboarding: v })} />
          <Check label="Send reminders" checked={s.modes.reminders} onChange={(v) => set("modes", { reminders: v })} />
          <Check label="Email invoices" checked={s.modes.invoice_emails} onChange={(v) => set("modes", { invoice_emails: v })} />
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <select aria-label="When payment opens" className={selectClass} value={s.modes.payment_order} onChange={(e) => set("modes", { payment_order: e.target.value as OnboardingSettings["modes"]["payment_order"] })}>
            <option value="after_submission">Pay after submitting documents</option>
            <option value="after_document_approval">Pay only after documents are verified</option>
          </select>
          <select aria-label="LMS access" className={selectClass} value={s.modes.lms_access} onChange={(e) => set("modes", { lms_access: e.target.value as "manual" | "automatic" })}>
            <option value="manual">LMS access granted by staff</option>
            <option value="automatic">LMS access granted automatically when eligible</option>
          </select>
        </div>
      </Section>

      <Section title="Fees" hint={finance ? "Shown to the student before they accept. Amounts in rupees with up to two decimals." : "Only staff with the finance permission can change fees."}>
        <div className="grid gap-3 sm:grid-cols-3">
          {([["base_amount", "Fee"], ["discount_amount", "Discount"], ["tax_rate_percent", "Tax rate %"]] as const).map(([k, label]) => (
            <div key={k} className="space-y-1.5">
              <Label htmlFor={`fee-${k}`}>{label}</Label>
              <Input id={`fee-${k}`} inputMode="decimal" disabled={!finance} value={s.fees[k]} onChange={(e) => set("fees", { [k]: e.target.value })} />
            </div>
          ))}
          <div className="space-y-1.5">
            <Label htmlFor="fee-tax">Tax treatment</Label>
            <select id="fee-tax" className={selectClass} disabled={!finance} value={s.fees.tax_mode} onChange={(e) => set("fees", { tax_mode: e.target.value as OnboardingSettings["fees"]["tax_mode"] })}>
              <option value="none">No tax shown</option>
              <option value="exclusive">Added on top</option>
              <option value="inclusive">Included in the fee</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="fee-late">Late fee</Label>
            <select id="fee-late" className={selectClass} disabled={!finance} value={s.fees.late_fee.mode} onChange={(e) => set("fees", { late_fee: { ...s.fees.late_fee, mode: e.target.value as "none" | "fixed" | "percent" } })}>
              <option value="none">None</option>
              <option value="fixed">Fixed amount</option>
              <option value="percent">Percentage</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="fee-late-value">Late fee value</Label>
            <Input id="fee-late-value" inputMode="decimal" disabled={!finance || s.fees.late_fee.mode === "none"} value={s.fees.late_fee.value} onChange={(e) => set("fees", { late_fee: { ...s.fees.late_fee, value: e.target.value } })} />
          </div>
        </div>
        <Input aria-label="Fee description" disabled={!finance} value={s.fees.description} onChange={(e) => set("fees", { description: e.target.value })} />
        <div className="flex flex-wrap gap-4">
          <Check label="Online (Cashfree)" disabled={!finance} checked={s.fees.methods.includes("cashfree")} onChange={(v) => toggleMethod("cashfree", v)} />
          <Check label="Bank transfer" disabled={!finance} checked={s.fees.methods.includes("bank_transfer")} onChange={(v) => toggleMethod("bank_transfer", v)} />
          <Check label="UPI" disabled={!finance} checked={s.fees.methods.includes("upi")} onChange={(v) => toggleMethod("upi", v)} />
        </div>
        <p className="text-xs text-muted-foreground">Saved fee: {money(view.fee_preview.total)} payable (tax {money(view.fee_preview.tax)}).</p>
      </Section>

      {finance && (
        <Section title="Payment accounts" hint="Shown only to students whose payment is open. Changes are logged.">
          <Check label="Bank transfer details" checked={s.payment_accounts.bank !== null} onChange={(v) => set("payment_accounts", { bank: v ? { holder: "", bank: "", account_number: "", ifsc: "", branch: "", instructions: "" } : null })} />
          {s.payment_accounts.bank && (
            <div className="grid gap-2 sm:grid-cols-3">
              {(["holder", "bank", "account_number", "ifsc", "branch", "instructions"] as const).map((k) => (
                <Input key={k} aria-label={k.replace("_", " ")} placeholder={k.replace("_", " ")} value={s.payment_accounts.bank?.[k] ?? ""}
                  onChange={(e) => set("payment_accounts", { bank: { ...s.payment_accounts.bank!, [k]: k === "ifsc" ? e.target.value.toUpperCase() : e.target.value } })} />
              ))}
            </div>
          )}
          <Check label="UPI details" checked={s.payment_accounts.upi !== null} onChange={(v) => set("payment_accounts", { upi: v ? { vpa: "", beneficiary: "", instructions: "" } : null })} />
          {s.payment_accounts.upi && (
            <div className="grid gap-2 sm:grid-cols-3">
              {(["vpa", "beneficiary", "instructions"] as const).map((k) => (
                <Input key={k} aria-label={k} placeholder={k === "vpa" ? "UPI ID (name@bank)" : k} value={s.payment_accounts.upi?.[k] ?? ""}
                  onChange={(e) => set("payment_accounts", { upi: { ...s.payment_accounts.upi!, [k]: e.target.value } })} />
              ))}
            </div>
          )}
        </Section>
      )}

      {finance && (
        <Section title="Receipts and invoices" hint="Without a GSTIN, students get payment receipts. A tax invoice is issued only when a GSTIN and a tax treatment are set.">
          <div className="grid gap-2 sm:grid-cols-2">
            <Input aria-label="Legal name" placeholder="Legal name (defaults to the organization name)" value={s.issuer.legal_name} onChange={(e) => set("issuer", { legal_name: e.target.value })} />
            <Input aria-label="GSTIN" placeholder="GSTIN (optional)" value={s.issuer.gstin ?? ""} onChange={(e) => set("issuer", { gstin: e.target.value.toUpperCase() || null })} />
            <Input aria-label="Address" placeholder="Address" value={s.issuer.address} onChange={(e) => set("issuer", { address: e.target.value })} />
            <Input aria-label="Receipt number prefix" placeholder="RCPT" value={s.issuer.receipt_prefix} onChange={(e) => set("issuer", { receipt_prefix: e.target.value.toUpperCase() })} />
            <Input aria-label="Footer" placeholder="Footer line (optional)" value={s.issuer.footer} onChange={(e) => set("issuer", { footer: e.target.value })} />
          </div>
        </Section>
      )}

      <Section title="Deadlines" hint={`Times are saved exactly and shown to students in ${s.deadlines.timezone}.`}>
        <div className="grid gap-3 sm:grid-cols-3">
          {dt("opens_at", "Opens")}
          {dt("closes_at", "Closes")}
          {dt("acceptance_deadline", "Accept by (optional)")}
          {dt("documents_deadline", "Documents by (optional)")}
          {dt("payment_deadline", "Pay by (optional)")}
          <div className="space-y-1.5">
            <Label htmlFor="dl-grace">Payment grace (hours)</Label>
            <Input id="dl-grace" type="number" min={0} value={s.deadlines.payment_grace_hours} onChange={(e) => set("deadlines", { payment_grace_hours: Number(e.target.value) || 0 })} />
          </div>
        </div>
        <Input aria-label="Time zone" value={s.deadlines.timezone} onChange={(e) => set("deadlines", { timezone: e.target.value })} />
      </Section>

      <Section title="Documents" hint="Aadhaar is not requested by default. Mark identity documents as sensitive: only reviewers can open them.">
        {s.documents.map((d, i) => (
          <div key={i} className="grid gap-2 rounded-md border p-2 sm:grid-cols-[1fr_auto]">
            <div className="space-y-2">
              <Input aria-label="Document name" value={d.label} onChange={(e) => setDoc(i, { label: e.target.value })} />
              <Input aria-label="Instructions" placeholder="Instructions for the student" value={d.instructions ?? ""} onChange={(e) => setDoc(i, { instructions: e.target.value })} />
              <div className="flex flex-wrap gap-3">
                <Check label="Required" checked={d.required ?? true} onChange={(v) => setDoc(i, { required: v })} />
                <Check label="Sensitive" checked={d.sensitive ?? false} onChange={(v) => setDoc(i, { sensitive: v })} />
                {(["pdf", "jpg", "png"] as const).map((t) => (
                  <Check key={t} label={t.toUpperCase()} checked={(d.types ?? ["pdf", "jpg", "png"]).includes(t)}
                    onChange={(v) => setDoc(i, { types: v ? [...new Set([...(d.types ?? []), t])] : (d.types ?? ["pdf", "jpg", "png"]).filter((x) => x !== t) })} />
                ))}
                <label className="flex items-center gap-1 text-sm">
                  Max MB
                  <Input className="w-16" type="number" min={1} max={15} value={d.max_mb ?? 5} onChange={(e) => setDoc(i, { max_mb: Number(e.target.value) || 5 })} />
                </label>
              </div>
            </div>
            <div className="flex gap-1 sm:flex-col">
              <Button size="sm" variant="ghost" aria-label="Move up" onClick={() => setS({ ...s, documents: move(s.documents, i, -1) })}><ArrowUp className="h-4 w-4" /></Button>
              <Button size="sm" variant="ghost" aria-label="Move down" onClick={() => setS({ ...s, documents: move(s.documents, i, 1) })}><ArrowDown className="h-4 w-4" /></Button>
              <Button size="sm" variant="ghost" aria-label="Remove" onClick={() => setS({ ...s, documents: s.documents.filter((_, j) => j !== i) })}><Trash2 className="h-4 w-4" /></Button>
            </div>
          </div>
        ))}
        <Button size="sm" variant="outline" onClick={() => setS({ ...s, documents: [...s.documents, { key: slugKey("document", new Set(s.documents.map((d) => d.key))), label: "New document", required: true, types: ["pdf", "jpg", "png"], max_mb: 5 }] })}>
          <Plus className="h-4 w-4" />
          Add document
        </Button>
      </Section>

      <Section title="Form questions" hint="Extra questions after the student's details. Nothing typed here is ever run as code.">
        {s.form.map((f, i) => (
          <div key={i} className="grid gap-2 rounded-md border p-2 sm:grid-cols-[1fr_auto]">
            <div className="grid gap-2 sm:grid-cols-2">
              <Input aria-label="Question" value={f.label} onChange={(e) => setField(i, { label: e.target.value })} />
              <select aria-label="Answer type" className={selectClass} value={f.type} onChange={(e) => setField(i, { type: e.target.value as FieldType, options: CHOICE.includes(e.target.value as FieldType) ? f.options ?? [] : [] })}>
                {FIELD_TYPES.map(([v, l]) => (
                  <option key={v} value={v}>{l}</option>
                ))}
              </select>
              {CHOICE.includes(f.type) && (
                <Input aria-label="Options" placeholder="Options, separated by commas" value={(f.options ?? []).join(", ")}
                  onChange={(e) => setField(i, { options: e.target.value.split(",").map((o) => o.trim()).filter(Boolean) })} />
              )}
              <Input aria-label="Help text" placeholder="Help text" value={f.description ?? ""} onChange={(e) => setField(i, { description: e.target.value })} />
              <select aria-label="Show only when" className={selectClass} value={f.visible_if?.field ?? ""} onChange={(e) => setField(i, { visible_if: e.target.value ? { field: e.target.value, equals: f.visible_if?.equals ?? "" } : null })}>
                <option value="">Always shown</option>
                {s.form.filter((o) => o.key !== f.key).map((o) => (
                  <option key={o.key} value={o.key}>Only when “{o.label}” is…</option>
                ))}
              </select>
              {f.visible_if && (
                <Input aria-label="Required answer" placeholder="…this answer" value={String(f.visible_if.equals)} onChange={(e) => setField(i, { visible_if: { field: f.visible_if!.field, equals: e.target.value } })} />
              )}
              <div className="flex gap-3">
                <Check label="Required" checked={f.type === "declaration" || (f.required ?? false)} disabled={f.type === "declaration"} onChange={(v) => setField(i, { required: v })} />
                <Check label="Student can edit" checked={f.editable ?? true} onChange={(v) => setField(i, { editable: v })} />
              </div>
            </div>
            <div className="flex gap-1 sm:flex-col">
              <Button size="sm" variant="ghost" aria-label="Move up" onClick={() => setS({ ...s, form: move(s.form, i, -1) })}><ArrowUp className="h-4 w-4" /></Button>
              <Button size="sm" variant="ghost" aria-label="Move down" onClick={() => setS({ ...s, form: move(s.form, i, 1) })}><ArrowDown className="h-4 w-4" /></Button>
              <Button size="sm" variant="ghost" aria-label="Remove" onClick={() => setS({ ...s, form: s.form.filter((_, j) => j !== i) })}><Trash2 className="h-4 w-4" /></Button>
            </div>
          </div>
        ))}
        <Button size="sm" variant="outline" onClick={() => setS({ ...s, form: [...s.form, { key: slugKey("question", new Set(s.form.map((f) => f.key))), label: "New question", type: "short_text", required: false, editable: true }] })}>
          <Plus className="h-4 w-4" />
          Add question
        </Button>
      </Section>

      <Section title="Acceptance declaration" hint="The student must tick this to accept. Raise the terms version whenever the wording changes.">
        <Textarea aria-label="Declaration" rows={4} value={s.declaration.text} onChange={(e) => set("declaration", { text: e.target.value })} />
        <div className="grid gap-2 sm:grid-cols-2">
          <Input aria-label="Terms version" value={s.declaration.terms_version} onChange={(e) => set("declaration", { terms_version: e.target.value })} />
          <Input aria-label="Terms link" placeholder="Link to the full terms (optional)" value={s.declaration.terms_url ?? ""} onChange={(e) => set("declaration", { terms_url: e.target.value || null })} />
        </div>
      </Section>

      <Section title="Contact and completion">
        <div className="grid gap-2 sm:grid-cols-2">
          <Input aria-label="Contact email" placeholder="Contact email" value={s.communication.contact_email ?? ""} onChange={(e) => set("communication", { contact_email: e.target.value || null })} />
          <Input aria-label="Contact phone" placeholder="Contact phone" value={s.communication.contact_phone ?? ""} onChange={(e) => set("communication", { contact_phone: e.target.value || null })} />
          <Input aria-label="WhatsApp group link" placeholder="https://chat.whatsapp.com/…" value={s.communication.whatsapp_link ?? ""} onChange={(e) => set("communication", { whatsapp_link: e.target.value || null })} />
          <select aria-label="When to show the WhatsApp link" className={selectClass} value={s.communication.whatsapp_visibility} onChange={(e) => set("communication", { whatsapp_visibility: e.target.value as "after_completion" | "after_acceptance" })}>
            <option value="after_completion">Show the group link after onboarding is complete</option>
            <option value="after_acceptance">Show it once the offer is accepted</option>
          </select>
          <Input aria-label="Reminder days" placeholder="Reminder days before closing, e.g. 7, 3, 1" value={s.communication.reminder_days.join(", ")}
            onChange={(e) => set("communication", { reminder_days: e.target.value.split(",").map((d) => Number(d.trim())).filter((d) => d > 0) })} />
        </div>
        <Textarea aria-label="Next steps" rows={3} placeholder="Next steps shown when onboarding is complete" value={s.communication.next_steps} onChange={(e) => set("communication", { next_steps: e.target.value })} />
      </Section>

      <div className="sticky bottom-0 flex flex-wrap items-center gap-3 border-t bg-background py-3">
        <Button disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save settings"}
        </Button>
        {notice && <p className={`text-sm ${notice.ok ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`}>{notice.text}</p>}
      </div>
    </div>
  );
}
