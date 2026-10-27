import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { errorMessage } from "@/features/institutions/lib/format";
import {
  type OfferField,
  type OfferFieldKey,
  type OfferFont,
  type OfferSettings,
  offerKeys,
  offersApi,
} from "@/features/our-internships/api/our-internships-api";
import { PdfPageView } from "@/features/our-internships/components/pdf-page-view";
import {
  FIELD_ORDER,
  SAMPLE_TEXT,
  cssFont,
  layoutProblem,
  nudgeField,
  placeField,
  removeField,
  sameLayout,
  sortFields,
  updateField,
  withinPages,
} from "@/features/our-internships/lib/offer-layout";

const PAGE_WIDTH = 560;
const selectClass = "w-full rounded-md border bg-background px-2 py-1.5 text-sm";

const FONTS: { value: OfferFont; label: string }[] = [
  { value: "sans", label: "Sans-serif" },
  { value: "sans_bold", label: "Sans-serif bold" },
  { value: "serif", label: "Serif" },
  { value: "serif_bold", label: "Serif bold" },
];

/**
 * Say where each detail goes on the uploaded letter: choose a detail, then click the spot on the page. The text is
 * stamped there for every student. "Preview" makes a real sample PDF so the result is seen before anything is sent.
 */
export function OfferDesigner({ internshipId, settings }: { internshipId: string; settings: OfferSettings }) {
  const queryClient = useQueryClient();
  const saved = useMemo(() => sortFields(settings.layout?.fields ?? []), [settings.layout]);
  const [fields, setFields] = useState<OfferField[]>(saved);
  const [active, setActive] = useState<OfferFieldKey>("name");
  const [page, setPage] = useState(1);
  const pages = settings.template_pages ?? 1;

  useEffect(() => setFields(saved), [saved]);

  const template = useQuery({
    queryKey: offerKeys.template(internshipId, settings.template_size),
    queryFn: () => offersApi.templateBytes(internshipId),
    staleTime: Infinity,
  });

  const save = useMutation({
    mutationFn: () => offersApi.saveLayout(internshipId, fields),
    onSuccess: (next) => queryClient.setQueryData(offerKeys.settings(internshipId), next),
  });
  const preview = useMutation({ mutationFn: () => offersApi.previewSample(internshipId, fields) });

  const problem = layoutProblem(fields);
  const dirty = !sameLayout(fields, saved);
  const placed = new Map(fields.map((f) => [f.key, f]));
  const activeField = placed.get(active);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Where details go on the letter</CardTitle>
        <CardDescription>
          Choose a detail on the right, then click on the letter where it should be printed. Click again to move it.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-6 xl:flex-row">
          <div className="space-y-2">
            {pages > 1 && (
              <div className="flex flex-wrap items-center gap-2 text-sm" role="tablist" aria-label="Letter pages">
                {Array.from({ length: pages }, (_, i) => i + 1).map((n) => (
                  <Button key={n} type="button" size="sm" role="tab" aria-selected={page === n} variant={page === n ? "default" : "outline"} onClick={() => setPage(n)}>
                    Page {n}
                  </Button>
                ))}
              </div>
            )}
            {template.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading the letter...</p>
            ) : template.isError || !template.data ? (
              <p className="text-sm text-destructive">Could not load the letter.</p>
            ) : (
              <PdfPageView
                data={template.data}
                page={page}
                width={PAGE_WIDTH}
                onPick={(x, y) => setFields((current) => placeField(current, active, page, x, y))}
                onNudge={(dx, dy) => setFields((current) => nudgeField(current, active, dx, dy))}
              >
                {(size) =>
                  fields
                    .filter((f) => f.page === page)
                    .map((f) => (
                      <span
                        key={f.key}
                        className={`pointer-events-none absolute whitespace-nowrap rounded-sm outline-dashed outline-1 ${f.key === active ? "outline-blue-600 bg-blue-500/10" : "outline-blue-400/60"}`}
                        style={{
                          left: f.x * size.width,
                          top: f.y * size.height,
                          // the position is the text's baseline; lift the box so the baseline sits on the clicked point
                          transform: `translate(${f.align === "center" ? "-50%" : f.align === "right" ? "-100%" : "0"}, -85%)`,
                          fontSize: f.font_size * size.height,
                          lineHeight: 1,
                          color: f.color,
                          ...cssFont(f.font),
                        }}
                      >
                        {SAMPLE_TEXT[f.key]}
                      </span>
                    ))
                }
              </PdfPageView>
            )}
          </div>

          <div className="min-w-0 flex-1 space-y-4">
            <ul className="space-y-1" aria-label="Details to print">
              {FIELD_ORDER.map((key) => {
                const f = placed.get(key);
                return (
                  <li key={key} className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant={active === key ? "default" : "outline"}
                      size="sm"
                      className="flex-1 justify-start"
                      aria-pressed={active === key}
                      onClick={() => {
                        setActive(key);
                        if (f) setPage(f.page);
                      }}
                    >
                      {settings.field_labels[key]}
                      <span className="ml-auto text-xs opacity-80">{f ? `page ${f.page}` : key === "name" ? "required" : "not placed"}</span>
                    </Button>
                    {f && (
                      <Button type="button" variant="ghost" size="icon" aria-label={`Remove ${settings.field_labels[key]}`} onClick={() => setFields(removeField(fields, key))}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>

            {activeField ? (
              <div className="space-y-3 rounded-md border p-3">
                <p className="text-sm font-medium">{settings.field_labels[active]}</p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="of-font">Font</Label>
                    <select id="of-font" className={selectClass} value={activeField.font} onChange={(e) => setFields(updateField(fields, active, { font: e.target.value as OfferFont }))}>
                      {FONTS.map((f) => (
                        <option key={f.value} value={f.value}>
                          {f.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="of-align">Aligned</Label>
                    <select id="of-align" className={selectClass} value={activeField.align} onChange={(e) => setFields(updateField(fields, active, { align: e.target.value as OfferField["align"] }))}>
                      <option value="left">from the clicked point</option>
                      <option value="center">centred on it</option>
                      <option value="right">ending at it</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="of-size">Size</Label>
                    <input
                      id="of-size"
                      type="range"
                      min={0.008}
                      max={0.08}
                      step={0.001}
                      className="w-full"
                      value={activeField.font_size}
                      onChange={(e) => setFields(updateField(fields, active, { font_size: Number(e.target.value) }))}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="of-width">Longest line</Label>
                    <input
                      id="of-width"
                      type="range"
                      min={0.05}
                      max={1}
                      step={0.01}
                      className="w-full"
                      value={activeField.max_width}
                      onChange={(e) => setFields(updateField(fields, active, { max_width: Number(e.target.value) }))}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="of-color">Colour</Label>
                    <Input id="of-color" type="color" className="h-9 w-16 p-1" value={activeField.color} onChange={(e) => setFields(updateField(fields, active, { color: e.target.value }))} />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">Text longer than the line shrinks to fit rather than running off the page.</p>
              </div>
            ) : (
              <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                {settings.field_labels[active]} is not placed yet. Click on the letter where it should go.
              </p>
            )}

            {problem && <p className="text-sm text-destructive">{problem}</p>}
            {(save.isError || preview.isError) && <p className="text-sm text-destructive">{errorMessage(save.error ?? preview.error, "Could not do that.")}</p>}
            <div className="flex flex-wrap gap-2">
              <Button type="button" disabled={!dirty || !!problem || save.isPending} onClick={() => save.mutate(undefined, { onSuccess: () => setFields((f) => withinPages(f, pages)) })}>
                <Save className="h-4 w-4" />
                {save.isPending ? "Saving..." : dirty ? "Save positions" : "Saved"}
              </Button>
              <Button type="button" variant="outline" disabled={!!problem || fields.length === 0 || preview.isPending} onClick={() => preview.mutate()}>
                <Eye className="h-4 w-4" />
                {preview.isPending ? "Making the sample..." : "Preview a sample letter"}
              </Button>
            </div>
            {dirty && <p className="text-xs text-muted-foreground">You have unsaved changes. The preview shows them; releasing offers uses what is saved.</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
