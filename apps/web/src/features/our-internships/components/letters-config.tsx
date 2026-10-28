import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ImageUp, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { errorMessage, formatBytes } from "@/features/institutions/lib/format";
import {
  type AssetKind,
  type LetterConfig,
  type LetterSettings,
  lettersApi,
  letterKeys,
} from "@/features/our-internships/api/letters-api";
import { AreaField, CheckField, ColorField, Field, ListEditor, NumberField, SelectField, TextField } from "@/features/our-internships/components/letter-fields";
import { REASONS, moveBy, removeAt, replaceAt, setPath } from "@/features/our-internships/lib/letters";

const ALIGN = [
  { value: "left", label: "Left" },
  { value: "center", label: "Centre" },
  { value: "right", label: "Right" },
] as const;

/** Where a change is saved: only this internship (an override), or as the default every internship starts from. */
type Scope = "internship" | "defaults";

export function LettersConfig({
  internshipId,
  settings,
  draft,
  onDraft,
  dirty,
}: {
  internshipId: string;
  settings: LetterSettings;
  draft: LetterConfig;
  onDraft: (next: LetterConfig) => void;
  dirty: boolean;
}) {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<Scope>("internship");
  const [saved, setSaved] = useState<string | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: letterKeys.all(internshipId) });
  const save = useMutation({
    mutationFn: () => lettersApi.saveConfig(internshipId, draft, scope),
    onSuccess: (r) => {
      setSaved(r.message);
      void refresh();
    },
  });
  const reset = useMutation({
    mutationFn: () => lettersApi.resetConfig(internshipId),
    onSuccess: () => {
      setSaved("This internship now uses the defaults.");
      void refresh();
    },
  });
  useEffect(() => {
    if (dirty) setSaved(null);
  }, [dirty]);

  const set = (path: (string | number)[], value: unknown) => onDraft(setPath(draft, path, value));
  const c = draft;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Save</CardTitle>
          <CardDescription>
            Settings you save as the default are used by every internship, so you set the design up once. An internship can still
            override any part of it for itself.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="radio" name="scope" checked={scope === "internship"} onChange={() => setScope("internship")} />
              For this internship only
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" name="scope" checked={scope === "defaults"} onChange={() => setScope("defaults")} />
              As the default for every internship
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? "Saving..." : dirty ? "Save settings" : "Saved"}
            </Button>
            {settings.has_overrides && (
              <Button
                variant="outline"
                disabled={reset.isPending}
                onClick={() => {
                  if (window.confirm("Drop this internship's own changes and use the defaults again?")) reset.mutate();
                }}
              >
                Use the defaults again
              </Button>
            )}
            {settings.has_overrides && <Badge variant="info">This internship overrides some defaults</Badge>}
            {dirty && <span className="text-sm text-amber-700 dark:text-amber-400">You have changes that are not saved.</span>}
          </div>
          {saved && !dirty && <p className="text-sm text-emerald-700 dark:text-emerald-400">{saved}</p>}
          {(save.isError || reset.isError) && <p className="text-sm text-destructive">{errorMessage(save.error ?? reset.error, "Could not save.")}</p>}
          {settings.problems.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
              <p className="font-medium">Still to do before letters can be made:</p>
              <ul className="list-disc pl-5">
                {settings.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Company information</CardTitle>
          <CardDescription>Printed at the top of the letter and in the signature block. Change it here without redoing the design.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <TextField id="co-name" label="Company name" value={c.company.name} onChange={(v) => set(["company", "name"], v)} />
          <TextField id="co-address" label="Address" value={c.company.address} onChange={(v) => set(["company", "address"], v)} />
          <TextField id="co-phone" label="Phone number" value={c.company.phone} onChange={(v) => set(["company", "phone"], v)} />
          <TextField id="co-email" label="Email address" value={c.company.email} onChange={(v) => set(["company", "email"], v)} />
          <TextField id="co-site" label="Website" value={c.company.website} onChange={(v) => set(["company", "website"], v)} />
          <span className="hidden sm:block" />
          <TextField id="co-signer" label="Authorised signatory name" value={c.company.signatory_name} onChange={(v) => set(["company", "signatory_name"], v)} />
          <TextField id="co-designation" label="Authorised signatory designation" value={c.company.signatory_designation} onChange={(v) => set(["company", "signatory_designation"], v)} />
        </CardContent>
      </Card>

      <BrandingCard internshipId={internshipId} settings={settings} draft={c} set={set} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Internship details</CardTitle>
          <CardDescription>The programme the letter offers. Phases are free: add, change, reorder or remove them, for any length of programme.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField id="pr-name" label="Programme name" value={c.programme.name} placeholder={settings.internship_title} hint="Empty uses the internship's own name." onChange={(v) => set(["programme", "name"], v)} />
            <TextField id="pr-position" label="Position" value={c.programme.position} placeholder="Intern" onChange={(v) => set(["programme", "position"], v)} />
            <TextField id="pr-duration" label="Duration" value={c.programme.duration} placeholder="3 months" onChange={(v) => set(["programme", "duration"], v)} />
            <SelectField
              id="pr-type"
              label="Program type"
              value={c.programme.program_type}
              onChange={(v) => set(["programme", "program_type"], v)}
              options={[
                { value: "unpaid", label: "Unpaid" },
                { value: "paid", label: "Paid" },
              ]}
            />
            <Field id="pr-start" label="Start date">
              <Input id="pr-start" type="date" value={c.programme.start_date ?? ""} onChange={(e) => set(["programme", "start_date"], e.target.value || null)} />
            </Field>
            <Field id="pr-end" label="End date">
              <Input id="pr-end" type="date" value={c.programme.end_date ?? ""} onChange={(e) => set(["programme", "end_date"], e.target.value || null)} />
            </Field>
            {c.programme.program_type === "paid" && <TextField id="pr-stipend" label="Stipend details" value={c.programme.stipend} onChange={(v) => set(["programme", "stipend"], v)} />}
          </div>
          <AreaField id="pr-desc" label="Programme description (optional)" value={c.programme.description} onChange={(v) => set(["programme", "description"], v)} />
          <div className="space-y-2">
            <p className="text-sm font-medium">Phases</p>
            {c.programme.phases.length === 0 && <p className="text-sm text-muted-foreground">No phases. The letter lists only the details above.</p>}
            {c.programme.phases.map((phase, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2">
                <Input className="w-32" aria-label={`Phase ${i + 1} label`} placeholder={`Month ${i + 1}`} value={phase.label} onChange={(e) => set(["programme", "phases"], replaceAt(c.programme.phases, i, { ...phase, label: e.target.value }))} />
                <Input className="min-w-[14rem] flex-1" aria-label={`Phase ${i + 1} title`} placeholder="Training & Skill Development" value={phase.title} onChange={(e) => set(["programme", "phases"], replaceAt(c.programme.phases, i, { ...phase, title: e.target.value }))} />
                <Button type="button" size="icon" variant="ghost" aria-label={`Move phase ${i + 1} up`} disabled={i === 0} onClick={() => set(["programme", "phases"], moveBy(c.programme.phases, i, -1))}>
                  <ArrowUp className="h-3.5 w-3.5" />
                </Button>
                <Button type="button" size="icon" variant="ghost" aria-label={`Move phase ${i + 1} down`} disabled={i === c.programme.phases.length - 1} onClick={() => set(["programme", "phases"], moveBy(c.programme.phases, i, 1))}>
                  <ArrowDown className="h-3.5 w-3.5" />
                </Button>
                <Button type="button" size="icon" variant="ghost" aria-label={`Remove phase ${i + 1}`} onClick={() => set(["programme", "phases"], removeAt(c.programme.phases, i))}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
            <Button type="button" size="sm" variant="outline" disabled={c.programme.phases.length >= 24} onClick={() => set(["programme", "phases"], [...c.programme.phases, { label: `Month ${c.programme.phases.length + 1}`, title: "" }])}>
              <Plus className="h-3.5 w-3.5" />
              Add a phase
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Letter content and terms</CardTitle>
          <CardDescription>
            The wording. Placeholders such as {"{{student_name}}"} are replaced for each student. Only what you write here is printed:
            nothing is added about money, rules or results.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <TextField id="ct-subject" label="Subject" value={c.content.subject} onChange={(v) => set(["content", "subject"], v)} />
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField id="ct-reason" label="Why the students were selected" value={c.content.selection_reason} onChange={(v) => set(["content", "selection_reason"], v)} options={REASONS} />
            <Field id="ct-date" label="Letter date" hint="Empty uses the day each letter is generated.">
              <Input id="ct-date" type="date" value={c.content.letter_date ?? ""} onChange={(e) => set(["content", "letter_date"], e.target.value || null)} />
            </Field>
          </div>
          {c.content.selection_reason === "custom" && <AreaField id="ct-custom" label="Your reason (one or two sentences)" value={c.content.custom_reason} onChange={(v) => set(["content", "custom_reason"], v)} />}
          <AreaField id="ct-intro" label="Introduction (optional)" rows={3} hint="Leave empty to write it from the reason above. Write your own to replace it completely." value={c.content.introduction} onChange={(v) => set(["content", "introduction"], v)} />
          <TextField id="ct-docs-intro" label="Lead-in to the documents" value={c.content.documents_intro} onChange={(v) => set(["content", "documents_intro"], v)} />
          <ListEditor id="ct-docs" label="Required documents" items={c.content.documents} addLabel="Add a document" onChange={(v) => set(["content", "documents"], v)} rows={1} />
          <ListEditor id="ct-terms" label="Terms and conditions" items={c.content.terms} addLabel="Add a clause" onChange={(v) => set(["content", "terms"], v)} />
          <AreaField id="ct-confirm" label="Confirmation text" value={c.content.confirmation} onChange={(v) => set(["content", "confirmation"], v)} />
          <AreaField id="ct-closing" label="Closing paragraph" value={c.content.closing} onChange={(v) => set(["content", "closing"], v)} />
          <AreaField id="ct-accept" label="Acceptance statement" value={c.content.acceptance} onChange={(v) => set(["content", "acceptance"], v)} />
          <CheckField id="ct-guardian" label="Ask for a parent or guardian's signature" checked={c.content.guardian_required} onChange={(v) => set(["content", "guardian_required"], v)} hint="Adds the guardian's signature and date lines and the guardian consent sentence." />
          {c.content.guardian_required && <AreaField id="ct-guardian-text" label="Guardian consent sentence" value={c.content.guardian_acceptance} onChange={(v) => set(["content", "guardian_acceptance"], v)} />}
          <CheckField id="ct-regid" label="Show the student's registration ID" checked={c.content.show_registration_id} onChange={(v) => set(["content", "show_registration_id"], v)} hint="Only printed for students who have one." />
          <CheckField id="ct-newpage" label="Start the documentation on a new page" checked={c.content.start_documentation_on_new_page} onChange={(v) => set(["content", "start_documentation_on_new_page"], v)} hint="Like the reference letter. Longer content always flows onto more pages." />
          <ListEditor id="ct-notes" label="Additional notes" items={c.content.notes} addLabel="Add a note" onChange={(v) => set(["content", "notes"], v)} max={10} />

          <div className="space-y-3 rounded-md border p-4">
            <p className="text-sm font-medium">Financial note</p>
            <p className="text-xs text-muted-foreground">A fee the students are told about. It is never printed unless you switch it on and approve it here.</p>
            <CheckField id="fn-enabled" label="Include a financial note" checked={c.content.financial_note.enabled} onChange={(v) => set(["content", "financial_note", "enabled"], v)} />
            {c.content.financial_note.enabled && (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <TextField id="fn-amount" label="Amount" placeholder="INR 2,000/-" value={c.content.financial_note.amount} onChange={(v) => set(["content", "financial_note", "amount"], v)} />
                  <TextField id="fn-purpose" label="Purpose" placeholder="tools and software for your training" value={c.content.financial_note.purpose} onChange={(v) => set(["content", "financial_note", "purpose"], v)} />
                  <TextField id="fn-conditions" label="Payment conditions" value={c.content.financial_note.payment_conditions} onChange={(v) => set(["content", "financial_note", "payment_conditions"], v)} />
                  <TextField id="fn-refund" label="Refund terms" value={c.content.financial_note.refund_terms} onChange={(v) => set(["content", "financial_note", "refund_terms"], v)} />
                </div>
                <CheckField id="fn-approved" label="I approve this note being printed on every letter" checked={c.content.financial_note.approved} onChange={(v) => set(["content", "financial_note", "approved"], v)} />
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ branding

const IMAGE_ACCEPT = "image/png,image/jpeg,image/svg+xml,.png,.jpg,.jpeg,.svg";

function AssetRow({ internshipId, settings, kind, hint }: { internshipId: string; settings: LetterSettings; kind: AssetKind; hint: string }) {
  const queryClient = useQueryClient();
  const asset = settings.assets[kind];
  const [scope, setScope] = useState<"internship" | "defaults">("defaults");
  const refresh = () => queryClient.invalidateQueries({ queryKey: letterKeys.all(internshipId) });
  const upload = useMutation({ mutationFn: (file: File) => lettersApi.uploadAsset(internshipId, kind, file, scope), onSuccess: () => void refresh() });
  const remove = useMutation({ mutationFn: () => lettersApi.removeAsset(internshipId, kind, asset?.source ?? scope), onSuccess: () => void refresh() });
  const labels: Record<AssetKind, string> = { logo: "Company logo", watermark: "Background watermark", signature: "Authorised signature", stamp: "Company stamp (optional)", extra: "Additional branding image (optional)" };

  return (
    <div className="space-y-2 rounded-md border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{labels[kind]}</p>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
        {asset && (
          <div className="flex items-center gap-2">
            <Badge variant={asset.source === "internship" ? "info" : "secondary"}>{asset.source === "internship" ? "This internship" : "Default"}</Badge>
            <Button type="button" size="sm" variant="ghost" disabled={remove.isPending} onClick={() => remove.mutate()}>
              <Trash2 className="h-3.5 w-3.5" />
              Remove
            </Button>
          </div>
        )}
      </div>
      {asset && (
        <p className="text-xs text-muted-foreground">
          {asset.filename} ({formatBytes(asset.size_bytes)})
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Input aria-label={`Upload the ${labels[kind]}`} type="file" accept={IMAGE_ACCEPT} className="max-w-xs" disabled={upload.isPending} onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload.mutate(file);
          e.target.value = "";
        }} />
        <select aria-label={`Use the ${labels[kind]} for`} className="rounded-md border bg-background px-2 py-2 text-sm" value={scope} onChange={(e) => setScope(e.target.value as "internship" | "defaults")}>
          <option value="defaults">for every internship</option>
          <option value="internship">for this internship only</option>
        </select>
        {upload.isPending && <span className="text-xs text-muted-foreground">Uploading...</span>}
        <ImageUp className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      </div>
      {(upload.isError || remove.isError) && <p className="text-sm text-destructive">{errorMessage(upload.error ?? remove.error, "Could not do that.")}</p>}
    </div>
  );
}

function BrandingCard({ internshipId, settings, draft, set }: { internshipId: string; settings: LetterSettings; draft: LetterConfig; set: (path: (string | number)[], value: unknown) => void }) {
  const b = draft.branding;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Branding and assets</CardTitle>
        <CardDescription>
          PNG, JPG or SVG, up to 4 MB each. Uploaded images are kept and reused for every letter. The signature is only ever the image
          you upload here; none is created for you.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-3 lg:grid-cols-2">
          <AssetRow internshipId={internshipId} settings={settings} kind="logo" hint="Shown at the top of the first page, and small on the pages after it." />
          <AssetRow internshipId={internshipId} settings={settings} kind="watermark" hint="A large, faded image behind the text." />
          <AssetRow internshipId={internshipId} settings={settings} kind="signature" hint="Placed above the authorised signatory's name." />
          <AssetRow internshipId={internshipId} settings={settings} kind="stamp" hint="Printed next to the signature when switched on below." />
          <AssetRow internshipId={internshipId} settings={settings} kind="extra" hint="A small image in the footer, for example an accreditation mark." />
        </div>

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">Logo</legend>
          <CheckField id="lg-show" label="Show the logo" checked={b.logo.show} onChange={(v) => set(["branding", "logo", "show"], v)} />
          <div className="grid gap-4 sm:grid-cols-4">
            <SelectField id="lg-pos" label="Position" value={b.logo.position} onChange={(v) => set(["branding", "logo", "position"], v)} options={ALIGN} />
            <NumberField id="lg-w" label="Width (mm)" value={b.logo.width_mm} min={8} max={120} onChange={(v) => set(["branding", "logo", "width_mm"], v)} />
            <NumberField id="lg-h" label="Height (mm)" value={b.logo.height_mm} min={5} max={60} onChange={(v) => set(["branding", "logo", "height_mm"], v)} />
            <NumberField id="lg-sp" label="Spacing below (mm)" value={b.logo.spacing_mm} min={0} max={30} onChange={(v) => set(["branding", "logo", "spacing_mm"], v)} />
          </div>
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">Watermark</legend>
          <CheckField id="wm-show" label="Show the watermark" checked={b.watermark.show} onChange={(v) => set(["branding", "watermark", "show"], v)} />
          <div className="grid gap-4 sm:grid-cols-3">
            <NumberField id="wm-size" label="Size (% of page width)" value={b.watermark.size_percent} min={10} max={150} onChange={(v) => set(["branding", "watermark", "size_percent"], v)} />
            <NumberField id="wm-op" label="Opacity" value={b.watermark.opacity} min={0.02} max={0.4} step={0.01} hint="Keep it low so the text stays easy to read." onChange={(v) => set(["branding", "watermark", "opacity"], v)} />
            <SelectField id="wm-pos" label="Position" value={b.watermark.position} onChange={(v) => set(["branding", "watermark", "position"], v)} options={[{ value: "center", label: "Centre" }, { value: "top", label: "Top" }, { value: "bottom", label: "Bottom" }]} />
            <NumberField id="wm-x" label="Move right (mm)" value={b.watermark.offset_x_mm} min={-100} max={100} onChange={(v) => set(["branding", "watermark", "offset_x_mm"], v)} />
            <NumberField id="wm-y" label="Move up (mm)" value={b.watermark.offset_y_mm} min={-150} max={150} onChange={(v) => set(["branding", "watermark", "offset_y_mm"], v)} />
            <SelectField id="wm-pages" label="Show on" value={b.watermark.pages} onChange={(v) => set(["branding", "watermark", "pages"], v)} options={[{ value: "all", label: "Every page" }, { value: "first", label: "First page only" }, { value: "last", label: "Last page only" }]} />
          </div>
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">Signature and stamp</legend>
          <div className="grid gap-4 sm:grid-cols-4">
            <NumberField id="sg-w" label="Signature width (mm)" value={b.signature.width_mm} min={10} max={100} onChange={(v) => set(["branding", "signature", "width_mm"], v)} />
            <NumberField id="sg-h" label="Signature height (mm)" value={b.signature.height_mm} min={6} max={50} onChange={(v) => set(["branding", "signature", "height_mm"], v)} />
            <SelectField id="sg-pos" label="Position" value={b.signature.position} onChange={(v) => set(["branding", "signature", "position"], v)} options={ALIGN} />
            <NumberField id="sg-st" label="Stamp size (mm)" value={b.signature.stamp_size_mm} min={10} max={60} onChange={(v) => set(["branding", "signature", "stamp_size_mm"], v)} />
          </div>
          <CheckField id="sg-stamp" label="Print the company stamp next to the signature" checked={b.signature.show_stamp} onChange={(v) => set(["branding", "signature", "show_stamp"], v)} />
        </fieldset>

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">Text and page</legend>
          <div className="grid gap-4 sm:grid-cols-4">
            <ColorField id="tx-color" label="Brand colour" value={b.brand_color} onChange={(v) => set(["branding", "brand_color"], v)} />
            <SelectField id="tx-font" label="Font" value={b.font_family} onChange={(v) => set(["branding", "font_family"], v)} options={[{ value: "helvetica", label: "Helvetica (sans-serif)" }, { value: "times", label: "Times (serif)" }, { value: "courier", label: "Courier (typewriter)" }]} />
            <NumberField id="tx-size" label="Font size (pt)" value={b.font_size} min={8} max={14} step={0.5} onChange={(v) => set(["branding", "font_size"], v)} />
            <SelectField id="tx-align" label="Text alignment" value={b.text_align} onChange={(v) => set(["branding", "text_align"], v)} options={[{ value: "left", label: "Left" }, { value: "justify", label: "Justified" }]} />
            <NumberField id="mg-t" label="Top margin (mm)" value={b.margin_top_mm} min={8} max={40} onChange={(v) => set(["branding", "margin_top_mm"], v)} />
            <NumberField id="mg-b" label="Bottom margin (mm)" value={b.margin_bottom_mm} min={8} max={40} onChange={(v) => set(["branding", "margin_bottom_mm"], v)} />
            <NumberField id="mg-l" label="Left margin (mm)" value={b.margin_left_mm} min={10} max={40} onChange={(v) => set(["branding", "margin_left_mm"], v)} />
            <NumberField id="mg-r" label="Right margin (mm)" value={b.margin_right_mm} min={10} max={40} onChange={(v) => set(["branding", "margin_right_mm"], v)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField id="hd-text" label="Header line (pages after the first)" value={b.header_text} onChange={(v) => set(["branding", "header_text"], v)} />
            <TextField id="ft-text" label="Footer line (every page)" value={b.footer_text} onChange={(v) => set(["branding", "footer_text"], v)} />
          </div>
          <div className="flex flex-wrap gap-6">
            <CheckField id="ft-pages" label="Show page numbers" checked={b.show_page_numbers} onChange={(v) => set(["branding", "show_page_numbers"], v)} />
            <CheckField id="ft-extra" label="Show the additional branding image in the footer" checked={b.show_extra_image} onChange={(v) => set(["branding", "show_extra_image"], v)} />
          </div>
        </fieldset>
      </CardContent>
    </Card>
  );
}
