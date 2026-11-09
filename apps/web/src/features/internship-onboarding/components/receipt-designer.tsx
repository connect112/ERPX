import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/features/institutions/lib/format";
import { onboardingFlowApi } from "@/features/internship-onboarding/api";
import { PdfPane } from "@/features/internship-onboarding/components/pdf-pane";
import { Block, Field, IssuerBlock, LayoutBlock, SampleBlock, TitlesBlock, WordingBlock } from "@/features/internship-onboarding/components/receipt-designer-fields";
import { ReceiptImageSlot } from "@/features/internship-onboarding/components/receipt-image-slot";
import { designerKey } from "@/features/internship-onboarding/lib/designer-key";
import { KIND_LABELS, MANDATORY_PARTS, OPTIONAL_SECTIONS, brandColorProblem, sameDesign, sampleBody, sourceLabel, withPatch } from "@/features/internship-onboarding/lib/receipt-design";
import {
  type DesignerView,
  type HeaderAlign,
  type PreviewResult,
  type ReceiptAssetInfo,
  type ReceiptDesign,
  type ReceiptKind,
  receiptsApi,
} from "@/features/internship-onboarding/receipts-api";

type Scope = "internship" | "organization";
const selectClass = "w-full rounded-md border bg-background px-3 py-2 text-sm";

function ColorField({ id, label, value, onChange, disabled }: { id: string; label: string; value: string; onChange: (v: string) => void; disabled: boolean }) {
  const problem = id === "brand-color" ? brandColorProblem(value) : null;
  return (
    <Field id={id} label={label} error={problem}>
      <div className="flex items-center gap-2">
        <input type="color" aria-label={`${label} picker`} className="h-9 w-10 rounded border" disabled={disabled} value={/^#[0-9a-fA-F]{6}$/.test(value) ? value : "#000000"} onChange={(e) => onChange(e.target.value.toUpperCase())} />
        <Input id={id} value={value} disabled={disabled} aria-invalid={problem !== null} onChange={(e) => onChange(e.target.value)} />
      </div>
    </Field>
  );
}

/**
 * Receipt Designer: the settings on the left, a live PDF preview on the right. The preview is read-only: it takes no document number and stores
 * or sends nothing, and every page is marked as a sample. Saving changes only the documents issued afterwards.
 *
 * Your unsaved edits are the draft. The draft is replaced by the saved design only when YOU save, reset or apply a template (or when the saved
 * design changed elsewhere and you have no unsaved edits). A background refresh of the page's data, an uploaded image arriving, or the issuer
 * form being saved never touches it.
 */
export function ReceiptDesigner({ internshipId, view }: { internshipId: string; view: DesignerView }) {
  const queryClient = useQueryClient();
  const canEdit = view.can_edit;
  const [scope, setScope] = useState<Scope>("internship");
  const [draft, setDraft] = useState<ReceiptDesign>(view.effective.design);
  const [kind, setKind] = useState<ReceiptKind>(view.fee.invoices_issued ? "tax_invoice" : "receipt");
  const [source, setSource] = useState<"sample" | "transaction">("sample");
  const [transactionId, setTransactionId] = useState("");
  const [sample, setSample] = useState<Record<string, string>>({});
  const [templateId, setTemplateId] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [shown, setShown] = useState<PreviewResult | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const latest = useRef(0);

  const saved = scope === "organization" ? view.organization_design : view.internship_design;
  const dirty = !sameDesign(draft, saved?.design ?? view.effective.design);

  // --- keep the draft when the data around it is refreshed
  const serverSignature = `${view.effective.source}|${view.effective.version}|${view.internship_design?.version ?? 0}|${view.organization_design?.version ?? 0}`;
  const synced = useRef(serverSignature);
  const adoptNext = useRef(false); // set by this person's own save / reset / template: the saved design is then the new draft
  // "Unsaved" here means different from the design the draft was last taken from, not from the design that has just arrived
  const baseline = useRef(view.effective.design);
  const draftNow = useRef(draft);
  draftNow.current = draft;
  useEffect(() => {
    if (synced.current === serverSignature) return;
    synced.current = serverSignature;
    const unsaved = !sameDesign(draftNow.current, baseline.current);
    baseline.current = view.effective.design;
    if (adoptNext.current || !unsaved) {
      adoptNext.current = false;
      setDraft(view.effective.design);
    } else {
      setNotice({ ok: false, text: "A newer design was saved elsewhere. Your unsaved changes are kept; saving will replace it." });
    }
  }, [serverSignature, view.effective.design]);

  const payments = useQuery({
    queryKey: ["onboarding-flow", internshipId, "payments", "confirmed"],
    queryFn: () => onboardingFlowApi.payments(internshipId, "confirmed"),
    enabled: source === "transaction",
    retry: false,
  });

  const draw = useMutation({
    mutationFn: (body: Parameters<typeof receiptsApi.preview>[1]) => receiptsApi.preview(internshipId, body),
  });
  const refresh = useCallback(() => {
    if (source === "transaction" && !transactionId) return;
    const ticket = ++latest.current;
    draw.mutate(
      {
        design: draft,
        kind,
        source,
        transaction_id: source === "transaction" ? transactionId : undefined,
        sample: source === "sample" ? sampleBody(sample) : undefined,
      },
      {
        onSuccess: (r) => ticket === latest.current && (setShown(r), setPreviewError(null)),
        onError: (e) => ticket === latest.current && setPreviewError(errorMessage(e, "The preview could not be drawn.")),
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, kind, source, transactionId, sample, internshipId]);

  // redraw shortly after each change; an older answer that arrives late is ignored
  useEffect(() => {
    const timer = setTimeout(refresh, 700);
    return () => clearTimeout(timer);
  }, [refresh]);

  const reload = () => void queryClient.invalidateQueries({ queryKey: designerKey(internshipId) });
  const done = (text: string) => {
    setNotice({ ok: true, text });
    adoptNext.current = true;
    reload();
  };
  const fail = (e: unknown) => setNotice({ ok: false, text: errorMessage(e, "That did not work.") });
  /** An uploaded image joins the list in the cached page data; nothing is reloaded, so nothing of the draft can be replaced. */
  const addAsset = (asset: ReceiptAssetInfo) => {
    queryClient.setQueryData<DesignerView>(designerKey(internshipId), (old) => (old ? { ...old, assets: [asset, ...old.assets.filter((a) => a.id !== asset.id)] } : old));
    setNotice({ ok: true, text: "Image uploaded and selected. Save the design to use it on documents." });
  };

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
    onSuccess: () => (setTemplateName(""), setNotice({ ok: true, text: "Saved as a template." }), reload()),
    onError: fail,
  });
  const archive = useMutation({
    mutationFn: (id: string) => receiptsApi.archiveTemplate(internshipId, id),
    onSuccess: () => (setTemplateId(""), setNotice({ ok: true, text: "Template archived." }), reload()),
    onError: fail,
  });

  const set = <K extends keyof ReceiptDesign>(key: K, patch: Partial<ReceiptDesign[K]> | ReceiptDesign[K]) => setDraft((d) => withPatch(d, key, patch));
  const blocked = brandColorProblem(draft.branding.brand_color) !== null;
  const rows = (payments.data ?? []).filter((p) => p.status === "confirmed" && (p.kind === "payment" || p.kind === "refund"));

  // two columns only where the preview gets a useful width (a 1024px window leaves it under 300px); narrower windows stack them
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,27rem)_minmax(0,1fr)]">
      <div className="min-w-0 space-y-3 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto xl:pr-2" data-testid="settings-panel">
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

        <IssuerBlock internshipId={internshipId} issuer={view.issuer} canEdit={canEdit} onSaved={reload} />
        <p className="px-1 text-xs text-muted-foreground">{view.fee.invoices_issued ? "A tax invoice is issued for each payment." : "No GSTIN and tax treatment are set, so payments get a payment receipt."}</p>

        <TitlesBlock design={draft} canEdit={canEdit} set={set} />
        <WordingBlock design={draft} canEdit={canEdit} set={set} />

        <Block title="Branding and header">
          <ColorField id="brand-color" label="Brand colour" value={draft.branding.brand_color} disabled={!canEdit} onChange={(v) => set("branding", { brand_color: v })} />
          <ColorField id="accent-color" label="Accent colour (tables and totals)" value={draft.branding.accent_color} disabled={!canEdit} onChange={(v) => set("branding", { accent_color: v })} />
          <Field id="header-align" label="Header alignment">
            <select id="header-align" className={selectClass} disabled={!canEdit} value={draft.branding.header_align} onChange={(e) => set("branding", { header_align: e.target.value as HeaderAlign })}>
              <option value="left">Left: issuer on the left, document details on the right</option>
              <option value="center">Centred</option>
              <option value="right">Right: document details on the left, issuer on the right</option>
            </select>
          </Field>
          <Field id="header-text" label="Line under the issuer's name (optional)" hint="For example a trading name or tagline. The legal name is never replaced.">
            <Input id="header-text" value={draft.texts.header_text} disabled={!canEdit} maxLength={120} onChange={(e) => set("texts", { header_text: e.target.value })} />
          </Field>
          {(["website", "email", "phone"] as const).map((k) => (
            <Field key={k} id={`contact-${k}`} label={k === "website" ? "Website" : k === "email" ? "Contact email" : "Contact phone"}>
              <Input id={`contact-${k}`} value={draft.contacts[k]} disabled={!canEdit} maxLength={k === "phone" ? 30 : 120} onChange={(e) => set("contacts", { [k]: e.target.value })} />
            </Field>
          ))}
        </Block>

        <Block title="Images">
          <ReceiptImageSlot internshipId={internshipId} kind="logo" label="Company logo" slot={draft.logo} assets={view.assets} canEdit={canEdit} onChange={(p) => set("logo", p)} onUploaded={addAsset} alignable />
          <ReceiptImageSlot internshipId={internshipId} kind="signature" label="Authorized signature" slot={draft.signature} assets={view.assets} canEdit={canEdit} onChange={(p) => set("signature", p)} onUploaded={addAsset} />
          <ReceiptImageSlot internshipId={internshipId} kind="stamp" label="Company stamp" slot={draft.stamp} assets={view.assets} canEdit={canEdit} onChange={(p) => set("stamp", p)} onUploaded={addAsset} />
          <Field id="signatory" label="Signature caption">
            <Input id="signatory" value={draft.signatory_label} disabled={!canEdit} maxLength={60} onChange={(e) => set("signatory_label", e.target.value)} />
          </Field>
        </Block>

        <LayoutBlock design={draft} canEdit={canEdit} set={set} />

        <Block title="Extra text" hint="Plain text only. Nothing typed here is ever run as code.">
          <Field id="thank-you" label="Thank-you message">
            <Textarea id="thank-you" rows={2} maxLength={300} disabled={!canEdit} value={draft.texts.thank_you} onChange={(e) => set("texts", { thank_you: e.target.value })} />
          </Field>
          <Field id="description-note" label="Note under the description (optional)" hint="The description itself comes from the accepted fee and is changed in the finance settings.">
            <Textarea id="description-note" rows={2} maxLength={300} disabled={!canEdit} value={draft.texts.description_note} onChange={(e) => set("texts", { description_note: e.target.value })} />
          </Field>
          <Field id="terms" label="Terms or remark (optional)">
            <Textarea id="terms" rows={3} maxLength={600} disabled={!canEdit} value={draft.texts.terms} onChange={(e) => set("texts", { terms: e.target.value })} />
          </Field>
          <Field id="footer-text" label="Footer text">
            <Textarea id="footer-text" rows={3} maxLength={500} disabled={!canEdit} value={draft.texts.footer} onChange={(e) => set("texts", { footer: e.target.value })} />
          </Field>
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

        <SampleBlock values={sample} onChange={setSample} disabled={source !== "sample"} />

        {canEdit && (
          <div className="sticky bottom-0 border-t bg-background py-3">
            {/* the message floats above the bar, so showing or hiding it never changes the height of the panel or moves anything */}
            {notice && (
              <p
                className={`absolute inset-x-0 bottom-full mb-1 rounded-md border bg-background px-3 py-2 text-sm shadow ${notice.ok ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"}`}
                role={notice.ok ? "status" : "alert"}
              >
                {notice.text}
              </p>
            )}
            <div className="flex flex-wrap items-center gap-2">
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
              <span className={`text-xs text-amber-700 ${dirty ? "" : "invisible"}`}>Unsaved changes</span>
            </div>
          </div>
        )}
      </div>

      <div className="min-w-0 space-y-3 xl:sticky xl:top-2 xl:self-start">
        <div className="flex flex-wrap items-end gap-2">
          <Field id="preview-kind" label="Document">
            <select id="preview-kind" className={selectClass} value={kind} disabled={source === "transaction"} onChange={(e) => setKind(e.target.value as ReceiptKind)}>
              {(Object.keys(KIND_LABELS) as ReceiptKind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABELS[k]}
                </option>
              ))}
            </select>
          </Field>
          <Field id="preview-source" label="Data">
            <select id="preview-source" className={selectClass} value={source} onChange={(e) => setSource(e.target.value as "sample" | "transaction")}>
              <option value="sample">Sample data</option>
              <option value="transaction">A real confirmed payment</option>
            </select>
          </Field>
          {source === "transaction" && (
            <Field id="preview-payment" label="Payment">
              <select id="preview-payment" className={selectClass} value={transactionId} onChange={(e) => setTransactionId(e.target.value)}>
                <option value="">Choose a payment…</option>
                {rows.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.reference_number} · {p.kind} · {p.amount} {p.currency}
                  </option>
                ))}
              </select>
            </Field>
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
  const view = useQuery({ queryKey: designerKey(internshipId), queryFn: () => receiptsApi.designer(internshipId) });
  if (view.isError) return <p className="text-sm text-destructive">{errorMessage(view.error, "Could not load the receipt designer.")}</p>;
  if (!view.data) return <p className="text-sm text-muted-foreground">Loading…</p>;
  return <ReceiptDesigner internshipId={internshipId} view={view.data} />;
}
