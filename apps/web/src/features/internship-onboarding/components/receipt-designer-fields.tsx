import { useMutation } from "@tanstack/react-query";
import { ArrowDown, ArrowUp } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import { BODY_PART_LABELS, KIND_LABELS, KIND_TITLE_KEYS, LABEL_FIELDS, LABEL_GROUPS, movePart, titleProblem } from "@/features/internship-onboarding/lib/receipt-design";
import { type BodyPart, type HeaderAlign, type IssuerIdentity, type ReceiptDesign, type ReceiptKind, receiptsApi } from "@/features/internship-onboarding/receipts-api";

const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

export function Block({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-3 rounded-md border p-3">
      <legend className="px-1 text-sm font-semibold">{title}</legend>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {children}
    </fieldset>
  );
}

export function Field({ id, label, hint, error, children }: { id: string; label: string; hint?: string; error?: string | null; children: ReactNode }) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

type Setter = <K extends keyof ReceiptDesign>(key: K, patch: Partial<ReceiptDesign[K]> | ReceiptDesign[K]) => void;

/** The legal identity of the issuer. It is saved in the finance settings (`config.issuer`: versioned, validated, finance permission), not in the
 *  design, so there is exactly one record of it. */
export function IssuerBlock({ internshipId, issuer, canEdit, onSaved }: { internshipId: string; issuer: IssuerIdentity; canEdit: boolean; onSaved: () => void }) {
  const [form, setForm] = useState<IssuerIdentity>(issuer);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const dirty = JSON.stringify(form) !== JSON.stringify(issuer);
  useEffect(() => {
    if (!dirty) setForm(issuer); // a refreshed value arrives only while nothing of yours is waiting to be saved
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(issuer)]);
  const save = useMutation({
    mutationFn: () => receiptsApi.saveIssuer(internshipId, { ...form, gstin: form.gstin?.trim() ? form.gstin.trim().toUpperCase() : null }),
    onSuccess: (r) => (setNotice({ ok: true, text: r.message }), onSaved()),
    onError: (e) => setNotice({ ok: false, text: errorMessage(e, "The issuer details could not be saved.") }),
  });
  const set = (patch: Partial<IssuerIdentity>) => setForm((f) => ({ ...f, ...patch }));
  return (
    <Block title="Issuer identity (finance settings)" hint="The legal name, address and GSTIN are kept in this internship's finance settings, with a version history. Changing them affects only documents issued afterwards.">
      <Field id="iss-name" label="Legal name">
        <Input id="iss-name" value={form.legal_name} disabled={!canEdit} maxLength={200} onChange={(e) => set({ legal_name: e.target.value })} />
      </Field>
      <Field id="iss-address" label="Registered address">
        <Textarea id="iss-address" rows={2} value={form.address} disabled={!canEdit} maxLength={500} onChange={(e) => set({ address: e.target.value })} />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field id="iss-gstin" label="GSTIN" hint="Needs a tax treatment in the fee settings.">
          <Input id="iss-gstin" value={form.gstin ?? ""} disabled={!canEdit} maxLength={15} onChange={(e) => set({ gstin: e.target.value.toUpperCase() })} />
        </Field>
        <Field id="iss-prefix" label="Number prefix" hint="Numbers continue counting.">
          <Input id="iss-prefix" value={form.receipt_prefix} disabled={!canEdit} maxLength={12} onChange={(e) => set({ receipt_prefix: e.target.value.toUpperCase() })} />
        </Field>
      </div>
      <Field id="iss-footer" label="Footer line from the finance settings">
        <Input id="iss-footer" value={form.footer} disabled={!canEdit} maxLength={500} onChange={(e) => set({ footer: e.target.value })} />
      </Field>
      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="outline" disabled={!dirty || save.isPending || !form.legal_name.trim()} onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save issuer identity"}
          </Button>
          {notice && (
            <span className={`text-xs ${notice.ok ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`} role={notice.ok ? "status" : "alert"}>
              {notice.text}
            </span>
          )}
        </div>
      )}
    </Block>
  );
}

export function TitlesBlock({ design, canEdit, set }: { design: ReceiptDesign; canEdit: boolean; set: Setter }) {
  return (
    <Block title="Document titles" hint="Reword the title and add a subtitle for each type. A title can never say the document is a different kind: a tax invoice stays a tax invoice, a credit note a credit note.">
      {(Object.keys(KIND_LABELS) as ReceiptKind[]).map((kind) => {
        const keys = KIND_TITLE_KEYS[kind];
        const title = design.labels[keys.title];
        return (
          <div key={kind} className="space-y-2 rounded-md bg-muted/30 p-2">
            <p className="text-xs font-medium">{KIND_LABELS[kind]}</p>
            <Field id={`title-${kind}`} label="Title" error={titleProblem(kind, title)}>
              <Input id={`title-${kind}`} value={title} disabled={!canEdit} maxLength={40} aria-invalid={titleProblem(kind, title) !== null} onChange={(e) => set("labels", { [keys.title]: e.target.value })} />
            </Field>
            <Field id={`subtitle-${kind}`} label="Subtitle (optional)">
              <Input id={`subtitle-${kind}`} value={design.labels[keys.subtitle]} disabled={!canEdit} maxLength={120} onChange={(e) => set("labels", { [keys.subtitle]: e.target.value })} />
            </Field>
          </div>
        );
      })}
    </Block>
  );
}

export function WordingBlock({ design, canEdit, set }: { design: ReceiptDesign; canEdit: boolean; set: Setter }) {
  return (
    <Block title="Headings, labels and status wording" hint="Every fixed word on the document. Amounts, tax, dates, references and numbers always come from the verified payment and cannot be edited here.">
      {LABEL_GROUPS.map((group) => (
        <div key={group.title} className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">{group.title}</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {group.keys.map((key) => {
              const meta = LABEL_FIELDS[key];
              return (
                <Field key={key} id={`lab-${key}`} label={meta.label} hint={meta.hint} error={design.labels[key].trim() === "" ? "Cannot be empty." : null}>
                  <Input id={`lab-${key}`} value={design.labels[key]} disabled={!canEdit} maxLength={meta.max} onChange={(e) => set("labels", { [key]: e.target.value })} />
                </Field>
              );
            })}
          </div>
        </div>
      ))}
    </Block>
  );
}

const NUMBER_FIELDS: { key: keyof ReceiptDesign["style"]; label: string; min: number; max: number; step: number }[] = [
  { key: "body_size", label: "Body text size (pt)", min: 8, max: 12, step: 0.5 },
  { key: "title_size", label: "Title size (pt)", min: 12, max: 30, step: 1 },
  { key: "issuer_size", label: "Issuer name size (pt)", min: 10, max: 22, step: 1 },
  { key: "section_gap_mm", label: "Space between sections (mm)", min: 4, max: 14, step: 1 },
  { key: "margin_x_mm", label: "Side margins (mm)", min: 12, max: 25, step: 1 },
];

export function LayoutBlock({ design, canEdit, set }: { design: ReceiptDesign; canEdit: boolean; set: Setter }) {
  return (
    <Block title="Typography, spacing and layout">
      <div className="grid grid-cols-2 gap-2">
        {NUMBER_FIELDS.map(({ key, label, min, max, step }) => (
          <Field key={key} id={`style-${key}`} label={label} hint={`${min} to ${max}`}>
            <Input id={`style-${key}`} type="number" min={min} max={max} step={step} value={design.style[key] as number} disabled={!canEdit} onChange={(e) => e.target.value !== "" && set("style", { [key]: Number(e.target.value) })} />
          </Field>
        ))}
        <Field id="style-borders" label="Table borders">
          <select id="style-borders" className={selectClass} disabled={!canEdit} value={design.style.table_borders} onChange={(e) => set("style", { table_borders: e.target.value as "lines" | "grid" | "none" })}>
            <option value="lines">Lines between rows</option>
            <option value="grid">Full grid</option>
            <option value="none">No borders</option>
          </select>
        </Field>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" disabled={!canEdit} checked={design.style.header_rule} onChange={(e) => set("style", { header_rule: e.target.checked })} />
        Line under the header
      </label>
      <Field id="sig-align" label="Signature and stamp alignment">
        <select id="sig-align" className={selectClass} disabled={!canEdit} value={design.signature_align} onChange={(e) => set("signature_align", e.target.value as HeaderAlign)}>
          <option value="left">Left</option>
          <option value="center">Centre</option>
          <option value="right">Right</option>
        </select>
      </Field>
      <div className="space-y-1">
        <p className="text-sm font-medium">Order of the sections</p>
        <ol className="space-y-1">
          {design.body_order.map((part: BodyPart, i) => (
            <li key={part} className="flex items-center gap-2 rounded border px-2 py-1 text-sm">
              <span className="flex-1">{BODY_PART_LABELS[part]}</span>
              <Button type="button" size="sm" variant="ghost" aria-label={`Move ${BODY_PART_LABELS[part]} up`} disabled={!canEdit || i === 0} onClick={() => set("body_order", movePart(design.body_order, part, -1))}>
                <ArrowUp className="h-4 w-4" />
              </Button>
              <Button type="button" size="sm" variant="ghost" aria-label={`Move ${BODY_PART_LABELS[part]} down`} disabled={!canEdit || i === design.body_order.length - 1} onClick={() => set("body_order", movePart(design.body_order, part, 1))}>
                <ArrowDown className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ol>
        <p className="text-xs text-muted-foreground">The header comes first and the total always stays directly under the amounts table.</p>
      </div>
    </Block>
  );
}

const SAMPLE_FIELDS: { key: string; label: string }[] = [
  { key: "customer_name", label: "Customer name" },
  { key: "customer_email", label: "Customer email" },
  { key: "customer_mobile", label: "Customer mobile" },
  { key: "amount", label: "Amount paid (₹)" },
  { key: "description", label: "Description" },
  { key: "application_reference", label: "Application reference" },
  { key: "programme", label: "Programme name" },
  { key: "payment_method", label: "Payment method" },
  { key: "transaction_reference", label: "Transaction reference" },
];

/** Sample customer and payment details for the preview only. Never saved, never part of a design, and unavailable for a real payment. */
export function SampleBlock({ values, onChange, disabled }: { values: Record<string, string>; onChange: (next: Record<string, string>) => void; disabled: boolean }) {
  return (
    <details className="rounded-md border p-3">
      <summary className="cursor-pointer text-sm font-semibold">Sample details for the preview (not saved)</summary>
      <p className="mt-2 text-xs text-muted-foreground">These only change what the sample preview shows, to see how long names or other amounts look. They are never saved and never used on a real document.</p>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {SAMPLE_FIELDS.map(({ key, label }) => (
          <Field key={key} id={`sample-${key}`} label={label}>
            <Input id={`sample-${key}`} value={values[key] ?? ""} disabled={disabled} inputMode={key === "amount" ? "decimal" : undefined} onChange={(e) => onChange({ ...values, [key]: e.target.value })} />
          </Field>
        ))}
      </div>
    </details>
  );
}
