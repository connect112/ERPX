import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import { onboardingFlowApi } from "@/features/internship-onboarding/api";
import { PdfPane } from "@/features/internship-onboarding/components/pdf-pane";
import { ReceiptImageSlot } from "@/features/internship-onboarding/components/receipt-image-slot";
import { KIND_LABELS, MANDATORY_PARTS, OPTIONAL_SECTIONS, brandColorProblem, sameDesign, sourceLabel, withPatch } from "@/features/internship-onboarding/lib/receipt-design";
import {
  type DesignerView,
  type HeaderAlign,
  type PreviewResult,
  type ReceiptDesign,
  type ReceiptKind,
  receiptsApi,
} from "@/features/internship-onboarding/receipts-api";

type Scope = "internship" | "organization";
const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

function Block({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <fieldset className="space-y-3 rounded-md border p-3">
      <legend className="px-1 text-sm font-semibold">{title}</legend>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {children}
    </fieldset>
  );
}

function ColorField({ id, label, value, onChange, disabled }: { id: string; label: string; value: string; onChange: (v: string) => void; disabled: boolean }) {
  const problem = id === "brand-color" ? brandColorProblem(value) : null;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex items-center gap-2">
        <input type="color" aria-label={`${label} picker`} className="h-9 w-10 rounded border" disabled={disabled} value={/^#[0-9a-fA-F]{6}$/.test(value) ? value : "#000000"} onChange={(e) => onChange(e.target.value.toUpperCase())} />
        <Input id={id} value={value} disabled={disabled} aria-invalid={problem !== null} onChange={(e) => onChange(e.target.value)} />
      </div>
      {problem && (
        <p className="text-xs text-destructive" role="alert">
          {problem}
        </p>
      )}
    </div>
  );
}

/**
 * Receipt Designer: the settings on the left, a live PDF preview on the right. The preview is read-only: it takes no document number and
 * stores or sends nothing, and every page is marked as a sample. Saving changes only the documents issued afterwards.
 */
export function ReceiptDesigner({ internshipId, view }: { internshipId: string; view: DesignerView }) {
  const queryClient = useQueryClient();
  const canEdit = view.can_edit;
  const [scope, setScope] = useState<Scope>("internship");
  const [draft, setDraft] = useState<ReceiptDesign>(view.effective.design);
  const [kind, setKind] = useState<ReceiptKind>(view.fee.invoices_issued ? "tax_invoice" : "receipt");
  const [source, setSource] = useState<"sample" | "transaction">("sample");
  const [transactionId, setTransactionId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [shown, setShown] = useState<PreviewResult | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const latest = useRef(0);

  useEffect(() => setDraft(view.effective.design), [view]);

  const saved = scope === "organization" ? view.organization_design : view.internship_design;
  const dirty = !sameDesign(draft, saved?.design ?? view.effective.design);
  const payments = useQuery({
    queryKey: ["onboarding-flow", internshipId, "payments", "confirmed"],
    queryFn: () => onboardingFlowApi.payments(internshipId, "confirmed"),
    enabled: source === "transaction",
    retry: false,
  });

  const draw = useMutation({
    mutationFn: (body: { design: ReceiptDesign; kind: ReceiptKind; source: "sample" | "transaction"; transaction_id?: string }) => receiptsApi.preview(internshipId, body),
  });
  const refresh = useCallback(() => {
    if (source === "transaction" && !transactionId) return;
    const ticket = ++latest.current;
    draw.mutate(
      { design: draft, kind, source, transaction_id: source === "transaction" ? transactionId : undefined },
      {
        onSuccess: (r) => ticket === latest.current && (setShown(r), setPreviewError(null)),
        onError: (e) => ticket === latest.current && setPreviewError(errorMessage(e, "The preview could not be drawn.")),
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, kind, source, transactionId, internshipId]);

  // redraw shortly after each change; an older answer that arrives late is ignored
  useEffect(() => {
    const timer = setTimeout(refresh, 700);
    return () => clearTimeout(timer);
  }, [refresh]);

  const done = (text: string) => {
    setNotice({ ok: true, text });
    void queryClient.invalidateQueries({ queryKey: ["receipt-designer", internshipId] });
  };
  const fail = (e: unknown) => setNotice({ ok: false, text: errorMessage(e, "That did not work.") });
  const save = useMutation({
    mutationFn: () => receiptsApi.save(internshipId, scope, draft, saved?.version),
    onSuccess: (r) => done(`Saved as version ${r.version}. It applies to documents issued from now on; documents already issued are unchanged.`),
    onError: fail,
  });
  const reset = useMutation({
    mutationFn: () => receiptsApi.reset(internshipId, scope),
    onSuccess: () => done("Reset to the default. Documents already issued are unchanged."),
    onError: fail,
  });
  const apply = useMutation({
    mutationFn: (id: string) => receiptsApi.applyTemplate(internshipId, id, scope),
    onSuccess: () => done("Template applied. It applies to documents issued from now on."),
    onError: fail,
  });
  const makeTemplate = useMutation({
    mutationFn: () => receiptsApi.createTemplate(internshipId, templateName, draft),
    onSuccess: () => (setTemplateName(""), done("Saved as a template.")),
    onError: fail,
  });
  const archive = useMutation({
    mutationFn: (id: string) => receiptsApi.archiveTemplate(internshipId, id),
    onSuccess: () => (setTemplateId(""), done("Template archived.")),
    onError: fail,
  });

  const set = <K extends keyof ReceiptDesign>(key: K, patch: Partial<ReceiptDesign[K]> | ReceiptDesign[K]) => setDraft((d) => withPatch(d, key, patch));
  const blocked = brandColorProblem(draft.branding.brand_color) !== null;
  const rows = (payments.data ?? []).filter((p) => p.status === "confirmed" && (p.kind === "payment" || p.kind === "refund"));

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,27rem)_minmax(0,1fr)]">
      <div className="space-y-3 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto lg:pr-2">
        <div className="rounded-md bg-muted/40 p-3 text-sm">
          {view.effective.layout === "legacy" ? (
            <p role="note" data-testid="legacy-notice">
              <strong>No design has been saved yet.</strong> Receipts, tax invoices and credit notes are still issued with the original layout. The preview shows the
              Receipt Designer layout; it is used for documents only after you save a design. Documents already issued never change.
            </p>
          ) : (
            <p>
              Documents issued now use <strong>{sourceLabel(view.effective.source)}</strong>
              {view.effective.version ? ` (version ${view.effective.version})` : ""}. Changing a design affects only documents issued afterwards; issued documents never change.
            </p>
          )}
          {canEdit && (
            <div className="mt-2 space-y-1">
              <Label htmlFor="design-scope">Save this design for</Label>
              <select id="design-scope" className={selectClass} value={scope} onChange={(e) => setScope(e.target.value as Scope)}>
                <option value="internship">This internship only</option>
                <option value="organization">The organization's default (every internship without its own)</option>
              </select>
            </div>
          )}
          {!canEdit && <p className="mt-1 text-xs text-muted-foreground">You can look at the design and preview it. Changing it needs the finance management permission.</p>}
        </div>

        <Block title="Issuer identity" hint="The legal name, address and GSTIN come from this internship's finance settings (Settings, Receipts and invoices) and cannot be changed here.">
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Legal name</dt>
            <dd>{view.issuer.legal_name || "-"}</dd>
            <dt className="text-muted-foreground">Address</dt>
            <dd>{view.issuer.address || "-"}</dd>
            <dt className="text-muted-foreground">GSTIN</dt>
            <dd>{view.issuer.gstin ?? "none"}</dd>
            <dt className="text-muted-foreground">Number prefix</dt>
            <dd>{view.issuer.receipt_prefix}</dd>
          </dl>
          <p className="text-xs text-muted-foreground">{view.fee.invoices_issued ? "A tax invoice is issued for each payment." : "No GSTIN and tax treatment are set, so payments get a payment receipt."}</p>
        </Block>

        <Block title="Branding">
          <ColorField id="brand-color" label="Brand colour" value={draft.branding.brand_color} disabled={!canEdit} onChange={(v) => set("branding", { brand_color: v })} />
          <ColorField id="accent-color" label="Accent colour (tables and totals)" value={draft.branding.accent_color} disabled={!canEdit} onChange={(v) => set("branding", { accent_color: v })} />
          <div className="space-y-1">
            <Label htmlFor="header-align">Header alignment</Label>
            <select id="header-align" className={selectClass} disabled={!canEdit} value={draft.branding.header_align} onChange={(e) => set("branding", { header_align: e.target.value as HeaderAlign })}>
              <option value="left">Left: issuer on the left, document details on the right</option>
              <option value="center">Centred</option>
              <option value="right">Right: document details on the left, issuer on the right</option>
            </select>
          </div>
        </Block>

        <Block title="Images">
          <ReceiptImageSlot internshipId={internshipId} kind="logo" label="Company logo" slot={draft.logo} assets={view.assets} canEdit={canEdit} onChange={(p) => set("logo", p)} onUploaded={() => done("Image uploaded.")} />
          <ReceiptImageSlot internshipId={internshipId} kind="signature" label="Authorized signature" slot={draft.signature} assets={view.assets} canEdit={canEdit} onChange={(p) => set("signature", p)} onUploaded={() => done("Image uploaded.")} />
          <ReceiptImageSlot internshipId={internshipId} kind="stamp" label="Company stamp" slot={draft.stamp} assets={view.assets} canEdit={canEdit} onChange={(p) => set("stamp", p)} onUploaded={() => done("Image uploaded.")} />
          <div className="space-y-1">
            <Label htmlFor="signatory">Signature caption</Label>
            <Input id="signatory" value={draft.signatory_label} disabled={!canEdit} maxLength={60} onChange={(e) => set("signatory_label", e.target.value)} />
          </div>
        </Block>

        <Block title="Contact details" hint="Shown under the issuer's address. Optional.">
          {(["website", "email", "phone"] as const).map((k) => (
            <div key={k} className="space-y-1">
              <Label htmlFor={`contact-${k}`}>{k === "website" ? "Website" : k === "email" ? "Contact email" : "Contact phone"}</Label>
              <Input id={`contact-${k}`} value={draft.contacts[k]} disabled={!canEdit} maxLength={k === "phone" ? 30 : 120} onChange={(e) => set("contacts", { [k]: e.target.value })} />
            </div>
          ))}
        </Block>

        <Block title="Wording" hint="Plain text only. Nothing typed here is ever run as code.">
          <div className="space-y-1">
            <Label htmlFor="thank-you">Thank-you message</Label>
            <Textarea id="thank-you" rows={2} maxLength={300} disabled={!canEdit} value={draft.texts.thank_you} onChange={(e) => set("texts", { thank_you: e.target.value })} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="footer-text">Footer text</Label>
            <Textarea id="footer-text" rows={3} maxLength={500} disabled={!canEdit} value={draft.texts.footer} onChange={(e) => set("texts", { footer: e.target.value })} />
          </div>
        </Block>

        <Block title="What the document shows" hint="Switch optional parts on or off. The parts listed below are always shown.">
          <div className="grid gap-1">
            {OPTIONAL_SECTIONS.map(({ key, label }) => (
              <label key={key} className="flex items-center gap-2 text-sm">
                <input type="checkbox" disabled={!canEdit} checked={draft.sections[key]} onChange={(e) => set("sections", { [key]: e.target.checked })} />
                {label}
              </label>
            ))}
          </div>
          <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">
            {MANDATORY_PARTS.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </Block>

        <Block title="Templates" hint="Reusable designs for the whole organization.">
          <div className="flex flex-wrap gap-2">
            <select aria-label="Choose a template" className={`${selectClass} max-w-[14rem]`} value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
              <option value="">Choose a template…</option>
              {view.templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <Button type="button" size="sm" variant="outline" disabled={!canEdit || !templateId || apply.isPending} onClick={() => apply.mutate(templateId)}>
              Apply
            </Button>
            <Button type="button" size="sm" variant="ghost" disabled={!canEdit || !templateId || archive.isPending} onClick={() => archive.mutate(templateId)}>
              Archive
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Input aria-label="New template name" className="max-w-[14rem]" placeholder="New template name" value={templateName} disabled={!canEdit} onChange={(e) => setTemplateName(e.target.value)} />
            <Button type="button" size="sm" variant="outline" disabled={!canEdit || !templateName.trim() || blocked || makeTemplate.isPending} onClick={() => makeTemplate.mutate()}>
              Save as template
            </Button>
          </div>
        </Block>

        {canEdit && (
          <div className="sticky bottom-0 flex flex-wrap items-center gap-2 border-t bg-background py-3">
            <Button type="button" disabled={save.isPending || blocked || (!dirty && !!saved)} onClick={() => save.mutate()}>
              {save.isPending ? "Saving…" : "Save design"}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={reset.isPending || (scope === "internship" ? !view.internship_design : !view.organization_design)}
              onClick={() => window.confirm("Reset to the default design? Documents already issued are not changed.") && reset.mutate()}
            >
              Reset to default
            </Button>
            {dirty && <span className="text-xs text-amber-700">Unsaved changes</span>}
            {notice && (
              <p className={`w-full text-sm ${notice.ok ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`} role={notice.ok ? "status" : "alert"}>
                {notice.text}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="space-y-3 lg:sticky lg:top-2 lg:self-start">
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label htmlFor="preview-kind">Document</Label>
            <select id="preview-kind" className={selectClass} value={kind} disabled={source === "transaction"} onChange={(e) => setKind(e.target.value as ReceiptKind)}>
              {(Object.keys(KIND_LABELS) as ReceiptKind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABELS[k]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="preview-source">Data</Label>
            <select id="preview-source" className={selectClass} value={source} onChange={(e) => setSource(e.target.value as "sample" | "transaction")}>
              <option value="sample">Sample data</option>
              <option value="transaction">A real confirmed payment</option>
            </select>
          </div>
          {source === "transaction" && (
            <div className="space-y-1">
              <Label htmlFor="preview-payment">Payment</Label>
              <select id="preview-payment" className={selectClass} value={transactionId} onChange={(e) => setTransactionId(e.target.value)}>
                <option value="">Choose a payment…</option>
                {rows.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.reference_number} · {p.kind} · {p.amount} {p.currency}
                  </option>
                ))}
              </select>
            </div>
          )}
          <Button type="button" variant="outline" disabled={draw.isPending} onClick={refresh}>
            Refresh preview
          </Button>
        </div>
        <PdfPane
          title="Preview"
          blob={shown?.blob ?? null}
          pages={shown?.pages ?? null}
          note={shown?.watermark || null}
          filename={source === "sample" ? "receipt-sample.pdf" : "receipt-preview.pdf"}
          loading={draw.isPending}
          error={previewError}
        />
        <p className="text-xs text-muted-foreground">The preview is read-only: no document number is used, nothing is saved or emailed, and every page is marked so it cannot be mistaken for a real receipt.</p>
      </div>
    </div>
  );
}

/** Loads the designer's data and shows it; the screen under Onboarding Settings. */
export function ReceiptDesignerPanel({ internshipId }: { internshipId: string }) {
  const view = useQuery({ queryKey: ["receipt-designer", internshipId], queryFn: () => receiptsApi.designer(internshipId) });
  if (view.isError) return <p className="text-sm text-destructive">{errorMessage(view.error, "Could not load the receipt designer.")}</p>;
  if (!view.data) return <p className="text-sm text-muted-foreground">Loading…</p>;
  return <ReceiptDesigner internshipId={internshipId} view={view.data} />;
}
