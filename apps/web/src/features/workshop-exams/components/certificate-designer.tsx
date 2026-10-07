import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import "@/features/workshop-exams/components/certificate-fonts.css";
import { CertificateIdFormat } from "@/features/workshop-exams/components/certificate-id-format";
import {
  baselineOffset,
  FONT_CSS,
  measureText,
  PLAIN_FONTS,
  SCRIPT_FONTS,
} from "@/features/workshop-exams/lib/certificate-render";
import {
  type CertificateFont,
  type CertificateLayout,
  DEFAULT_CERTIFICATE_LAYOUT,
  type WorkshopExam,
  workshopExamsApi,
} from "@/features/workshop-exams/api/workshop-exams-api";

const SAMPLE_NAME = "Sample Student Name";

const FONT_GROUPS = (
  <>
    <optgroup label="Plain">
      {PLAIN_FONTS.map((key) => (
        <option key={key} value={key}>
          {FONT_CSS[key].label}
        </option>
      ))}
    </optgroup>
    <optgroup label="Script">
      {SCRIPT_FONTS.map((key) => (
        <option key={key} value={key}>
          {FONT_CSS[key].label}
        </option>
      ))}
    </optgroup>
  </>
);

const DEFAULT_GRADIENT_END = "#38bdf8";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

const clamp01 = (n: number) => Math.min(1, Math.max(0, n));

/** A believable ID for the preview, in the exam's format when it has a simple one. */
function previewId(pattern: string, start: number): string {
  const text = pattern.trim();
  if (!text) return "WS-2026-3F9A12C4";
  const year = String(new Date().getFullYear());
  return text.replace(/\{([^{}]*)\}/g, (_, raw: string) => {
    const token = raw.trim().toUpperCase();
    if (token === "YYYY") return year;
    if (token === "YY") return year.slice(2);
    if (token === "MM") return String(new Date().getMonth() + 1).padStart(2, "0");
    const counted = /^([#ADL])(\d{1,2})$/.exec(token);
    if (counted) {
      const n = Number(counted[2]);
      if (counted[1] === "#") return String(start).padStart(n, "0");
      const pool = counted[1] === "D" ? "0123456789" : counted[1] === "L" ? "ABCDEFGHJKMNPQRSTUVWXYZ" : "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
      return Array.from({ length: n }, (_x, i) => pool[(i * 7 + 3) % pool.length]).join("");
    }
    const range = /^(\d+)-(\d+)$/.exec(token);
    return range ? range[1] : "";
  });
}

/**
 * The admin uploads their finished certificate (without a name) and drags a
 * marker to where each student's name should be printed. Every student's
 * certificate is that image with their own name stamped there.
 */
export function CertificateDesigner({ exam }: { exam: WorkshopExam }) {
  const queryClient = useQueryClient();
  const locked = !!exam.certificates_dispatched_at;
  const [layout, setLayout] = useState<CertificateLayout>(exam.certificate_layout ?? DEFAULT_CERTIFICATE_LAYOUT);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageVersion, setImageVersion] = useState(0);
  const [boxSize, setBoxSize] = useState({ width: 0, height: 0 });
  const [testEmail, setTestEmail] = useState("");
  const [placing, setPlacing] = useState<"name" | "id">("name");
  const [fontsReady, setFontsReady] = useState(0);
  const [idPattern, setIdPattern] = useState(exam.certificate_id_pattern ?? "");
  const [idStart, setIdStart] = useState(exam.certificate_id_start);
  const boxRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const dragging = useRef(false);

  // Pull the stored artwork down as a blob (the endpoint needs the admin's token).
  useEffect(() => {
    if (!exam.has_certificate_template) {
      setImageUrl(null);
      return;
    }
    let cancelled = false;
    let created: string | null = null;
    workshopExamsApi
      .certificateTemplateImage(exam.id)
      .then((blob) => {
        if (cancelled) return;
        created = URL.createObjectURL(blob);
        setImageUrl(created);
      })
      .catch(() => !cancelled && setImageUrl(null));
    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [exam.id, exam.has_certificate_template, imageVersion]);

  // Sizes are fractions of the page, so track the preview's width and height.
  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    const update = () => setBoxSize({ width: box.clientWidth, height: box.clientHeight });
    const observer = new ResizeObserver(update);
    observer.observe(box);
    update();
    return () => observer.disconnect();
  }, [imageUrl]);

  // The script fonts load on demand; measure again once they have arrived.
  useEffect(() => {
    let cancelled = false;
    const families = SCRIPT_FONTS.map((key) => FONT_CSS[key].family.split(",")[0].replace(/'/g, ""));
    void Promise.all(families.map((family) => document.fonts.load(`32px "${family}"`).catch(() => []))).then(
      () => !cancelled && setFontsReady((n) => n + 1),
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });

  const upload = useMutation({
    mutationFn: (file: File) => workshopExamsApi.uploadCertificateTemplate(exam.id, file),
    onSuccess: (saved) => {
      setLayout(saved.certificate_layout ?? DEFAULT_CERTIFICATE_LAYOUT);
      setImageVersion((v) => v + 1);
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: () => workshopExamsApi.removeCertificateTemplate(exam.id),
    onSuccess: refresh,
  });
  const save = useMutation({
    mutationFn: () => workshopExamsApi.update(exam.id, { certificate_layout: layout }),
    onSuccess: refresh,
  });
  const idDraft = { ...(idPattern.trim() ? { id_pattern: idPattern.trim() } : {}), id_start: idStart };
  const preview = useMutation({
    mutationFn: () => workshopExamsApi.certificatePreviewPdf(exam.id, layout, idDraft),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    },
  });
  const sendTest = useMutation({
    mutationFn: () => workshopExamsApi.emailTestCertificate(exam.id, testEmail.trim(), layout, idDraft),
  });

  const place = useCallback((event: React.PointerEvent | PointerEvent) => {
    const box = boxRef.current;
    if (!box) return;
    const rect = box.getBoundingClientRect();
    const x = clamp01((event.clientX - rect.left) / rect.width);
    const y = clamp01((event.clientY - rect.top) / rect.height);
    setLayout((l) => (placing === "id" ? { ...l, id_x: x, id_y: y } : { ...l, name_x: x, name_y: y }));
  }, [placing]);

  const nudge = (event: React.KeyboardEvent) => {
    const step = event.shiftKey ? 0.01 : 0.002;
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    };
    const move = moves[event.key];
    if (!move || locked) return;
    event.preventDefault();
    setLayout((l) =>
      placing === "id"
        ? { ...l, id_x: clamp01(l.id_x + move[0]), id_y: clamp01(l.id_y + move[1]) }
        : { ...l, name_x: clamp01(l.name_x + move[0]), name_y: clamp01(l.name_y + move[1]) },
    );
  };

  const set = <K extends keyof CertificateLayout>(key: K, value: CertificateLayout[K]) =>
    setLayout((l) => ({ ...l, [key]: value }));

  const dirty = JSON.stringify(layout) !== JSON.stringify(exam.certificate_layout ?? DEFAULT_CERTIFICATE_LAYOUT);
  const font = FONT_CSS[layout.font];
  const sampleId = previewId(idPattern, idStart);

  // Where and how big the sample name and ID are drawn: shrink a long name like the PDF does, and put the
  // text's baseline (not its top) at the chosen point.
  const shown = useMemo(() => {
    void fontsReady;
    let nameSize = layout.font_size * boxSize.height;
    const limit = layout.max_width * boxSize.width;
    const floor = nameSize * 0.4;
    let nameMetrics = measureText(SAMPLE_NAME, layout.font, nameSize);
    if (nameMetrics.width > limit && nameMetrics.width > 0) {
      nameSize = Math.max(floor, (nameSize * limit) / nameMetrics.width);
      nameMetrics = measureText(SAMPLE_NAME, layout.font, nameSize);
    }
    const idSize = layout.id_font_size * boxSize.height;
    const idMetrics = measureText(sampleId, layout.id_font, idSize);
    return {
      nameSize,
      nameTop: layout.name_y * boxSize.height - baselineOffset(nameSize, nameMetrics.ascent, nameMetrics.descent),
      idSize,
      idTop: layout.id_y * boxSize.height - baselineOffset(idSize, idMetrics.ascent, idMetrics.descent),
    };
  }, [layout, boxSize, fontsReady, sampleId]);
  const idFont = FONT_CSS[layout.id_font];
  const gradient = layout.color_end && layout.color_end.toLowerCase() !== layout.color.toLowerCase();

  return (
    <div className="space-y-3">
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) upload.mutate(file);
          e.target.value = "";
        }}
      />

      <CertificateIdFormat
        examId={exam.id}
        savedPattern={exam.certificate_id_pattern}
        savedStart={exam.certificate_id_start}
        pattern={idPattern}
        start={idStart}
        onPattern={setIdPattern}
        onStart={setIdStart}
        locked={locked}
      />

      {!exam.has_certificate_template ? (
        <div className="rounded-md border border-dashed p-4 text-sm">
          <p className="font-medium">Use your own certificate design</p>
          <p className="mt-1 text-muted-foreground">
            Upload the finished certificate as a PNG or JPG <strong>without a name</strong>. You then click where
            the name goes, and each student's name is printed there automatically before it is emailed.
          </p>
          <Button
            className="mt-3"
            variant="outline"
            disabled={upload.isPending || locked}
            onClick={() => fileRef.current?.click()}
          >
            {upload.isPending ? "Uploading..." : "Upload certificate image"}
          </Button>
        </div>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Click or drag on the certificate to place the {placing === "id" ? "certificate ID" : "name"} (arrow keys
            nudge it). The text shown is only a sample - use "Preview PDF" to see exactly what students get.
          </p>
          {layout.show_id && (
            <div className="flex items-center gap-2 text-sm" role="group" aria-label="What to move">
              <span className="text-muted-foreground">Moving:</span>
              {(["name", "id"] as const).map((target) => (
                <Button
                  key={target}
                  type="button"
                  size="sm"
                  variant={placing === target ? "default" : "outline"}
                  onClick={() => setPlacing(target)}
                >
                  {target === "name" ? "Student name" : "Certificate ID"}
                </Button>
              ))}
            </div>
          )}

          <div
            ref={boxRef}
            tabIndex={0}
            role="slider"
            aria-label={`Position of the ${placing === "id" ? "certificate ID" : "student name"} on the certificate`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round((placing === "id" ? layout.id_x : layout.name_x) * 100)}
            aria-valuetext={`${Math.round((placing === "id" ? layout.id_x : layout.name_x) * 100)}% from the left, ${Math.round((placing === "id" ? layout.id_y : layout.name_y) * 100)}% from the top`}
            className="relative touch-none select-none overflow-hidden rounded-md border outline-none focus-visible:ring-2 focus-visible:ring-ring"
            style={{ cursor: locked ? "default" : "crosshair" }}
            onPointerDown={(e) => {
              if (locked) return;
              dragging.current = true;
              e.currentTarget.setPointerCapture(e.pointerId);
              place(e);
            }}
            onPointerMove={(e) => dragging.current && place(e)}
            onPointerUp={() => (dragging.current = false)}
            onPointerCancel={() => (dragging.current = false)}
            onKeyDown={nudge}
          >
            {imageUrl ? (
              <img src={imageUrl} alt="Certificate design" className="block w-full" draggable={false} />
            ) : (
              <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">Loading design...</div>
            )}
            {imageUrl && (
              <>
                <span
                  className="pointer-events-none absolute whitespace-nowrap"
                  style={{
                    left: `${layout.name_x * 100}%`,
                    top: `${shown.nameTop}px`,
                    transform: "translateX(-50%)",
                    fontSize: `${shown.nameSize}px`,
                    lineHeight: 1,
                    padding: "0 0.12em",
                    fontFamily: font.family,
                    fontStyle: font.style,
                    fontWeight: font.weight,
                    fontSynthesis: "none",
                    ...(gradient
                      ? {
                          backgroundImage: `linear-gradient(90deg, ${layout.color}, ${layout.color_end})`,
                          WebkitBackgroundClip: "text",
                          backgroundClip: "text",
                          WebkitTextFillColor: "transparent",
                          color: "transparent",
                        }
                      : { color: layout.color }),
                    outline: placing === "name" ? "1px dashed rgba(37, 99, 235, 0.7)" : "none",
                    outlineOffset: "2px",
                  }}
                >
                  {SAMPLE_NAME}
                </span>
                <span
                  className="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-600 ring-2 ring-white"
                  style={{ left: `${layout.name_x * 100}%`, top: `${layout.name_y * 100}%` }}
                />
                {layout.show_id && (
                  <>
                    <span
                      className="pointer-events-none absolute whitespace-nowrap"
                      style={{
                        left: `${layout.id_x * 100}%`,
                        top: `${shown.idTop}px`,
                        fontSize: `${shown.idSize}px`,
                        lineHeight: 1,
                        fontFamily: idFont.family,
                        fontStyle: idFont.style,
                        fontWeight: idFont.weight,
                        fontSynthesis: "none",
                        color: layout.id_color,
                        outline: placing === "id" ? "1px dashed rgba(5, 150, 105, 0.8)" : "none",
                        outlineOffset: "2px",
                      }}
                    >
                      {sampleId}
                    </span>
                    <span
                      className="pointer-events-none absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-600/80 ring-2 ring-white"
                      style={{ left: `${layout.id_x * 100}%`, top: `${layout.id_y * 100}%` }}
                    />
                  </>
                )}
              </>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="cd-font">Font</Label>
              <select
                id="cd-font"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                disabled={locked}
                value={layout.font}
                onChange={(e) => set("font", e.target.value as CertificateFont)}
              >
                {FONT_GROUPS}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="cd-color">{layout.color_end !== null ? "Gradient starts with" : "Text colour"}</Label>
              <input
                id="cd-color"
                type="color"
                className="h-9 w-full rounded-md border bg-background p-1"
                disabled={locked}
                value={layout.color}
                onChange={(e) => set("color", e.target.value)}
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  disabled={locked}
                  checked={layout.color_end !== null}
                  onChange={(e) => set("color_end", e.target.checked ? DEFAULT_GRADIENT_END : null)}
                />
                <span>Gradient text (fades from the first colour on the left to a second colour on the right)</span>
              </label>
              {layout.color_end !== null && (
                <div className="flex items-center gap-2">
                  <Label htmlFor="cd-color-end" className="text-sm">
                    Gradient ends with
                  </Label>
                  <input
                    id="cd-color-end"
                    type="color"
                    className="h-9 w-24 rounded-md border bg-background p-1"
                    disabled={locked}
                    value={layout.color_end}
                    onChange={(e) => set("color_end", e.target.value)}
                  />
                </div>
              )}
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={locked}
                onClick={() =>
                  setLayout((l) => ({ ...l, font: "great_vibes", color: "#1e3a8a", color_end: DEFAULT_GRADIENT_END }))
                }
              >
                Try: elegant blue script
              </Button>
            </div>
            <div className="space-y-1">
              <Label htmlFor="cd-size">Text size</Label>
              <input
                id="cd-size"
                type="range"
                min={2}
                max={20}
                step={0.5}
                className="w-full"
                disabled={locked}
                value={layout.font_size * 100}
                onChange={(e) => set("font_size", Number(e.target.value) / 100)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="cd-width">Longest name allowed to span</Label>
              <input
                id="cd-width"
                type="range"
                min={20}
                max={100}
                step={1}
                className="w-full"
                disabled={locked}
                value={layout.max_width * 100}
                onChange={(e) => set("max_width", Number(e.target.value) / 100)}
              />
              <p className="text-xs text-muted-foreground">Longer names shrink to fit inside this width.</p>
            </div>
          </div>

          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5"
              disabled={locked}
              checked={layout.show_verification}
              onChange={(e) => set("show_verification", e.target.checked)}
            />
            <span>
              Print a small certificate number and verification QR in the bottom-right corner (leave that corner of
              your design empty).
            </span>
          </label>

          <div className="space-y-2 rounded-md border p-3">
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5"
                disabled={locked}
                checked={layout.show_id}
                onChange={(e) => {
                  set("show_id", e.target.checked);
                  setPlacing(e.target.checked ? "id" : "name");
                }}
              />
              <span>
                Print each certificate's ID on the design (for a spot like "Certificate ID: ____"). Then use
                "Moving: Certificate ID" above and click right after the label; the ID starts at that point.
              </span>
            </label>
            {layout.show_id && (
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-1">
                  <Label htmlFor="cd-id-font">ID font</Label>
                  <select
                    id="cd-id-font"
                    className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                    disabled={locked}
                    value={layout.id_font}
                    onChange={(e) => set("id_font", e.target.value as CertificateFont)}
                  >
                    {FONT_GROUPS}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="cd-id-color">ID colour</Label>
                  <input
                    id="cd-id-color"
                    type="color"
                    className="h-9 w-full rounded-md border bg-background p-1"
                    disabled={locked}
                    value={layout.id_color}
                    onChange={(e) => set("id_color", e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="cd-id-size">ID size</Label>
                  <input
                    id="cd-id-size"
                    type="range"
                    min={0.8}
                    max={5}
                    step={0.1}
                    className="w-full"
                    disabled={locked}
                    value={layout.id_font_size * 100}
                    onChange={(e) => set("id_font_size", Number(e.target.value) / 100)}
                  />
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button disabled={!dirty || save.isPending || locked} onClick={() => save.mutate()}>
              {save.isPending ? "Saving..." : "Save design"}
            </Button>
            <Button variant="outline" disabled={preview.isPending} onClick={() => preview.mutate()}>
              {preview.isPending ? "Preparing..." : "Preview PDF"}
            </Button>
            <Button variant="outline" disabled={upload.isPending || locked} onClick={() => fileRef.current?.click()}>
              Replace image
            </Button>
            <Button
              variant="ghost"
              className="text-destructive"
              disabled={remove.isPending || locked}
              onClick={() => {
                if (window.confirm("Remove your design and go back to the automatic certificate?")) remove.mutate();
              }}
            >
              Remove image
            </Button>
          </div>
          {dirty && !locked && <p className="text-sm text-amber-700">You have unsaved changes to the design.</p>}
          {save.isSuccess && !dirty && <p className="text-sm text-muted-foreground">Design saved.</p>}

          <div className="rounded-md border p-3">
            <Label htmlFor="cd-test">Send yourself a test certificate</Label>
            <div className="mt-2 flex gap-2">
              <Input
                id="cd-test"
                type="email"
                placeholder="you@example.com"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
              />
              <Button
                variant="outline"
                disabled={!testEmail.includes("@") || sendTest.isPending}
                onClick={() => sendTest.mutate()}
              >
                {sendTest.isPending ? "Sending..." : "Send test"}
              </Button>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Uses the design as shown above, with a sample name. Good for checking real email delivery before the
              workshop.
            </p>
            {sendTest.isSuccess && <p className="mt-2 text-sm text-emerald-700">{sendTest.data.message}</p>}
            {sendTest.isError && (
              <p className="mt-2 text-sm text-destructive">{errorMessage(sendTest.error, "Could not send.")}</p>
            )}
          </div>
        </>
      )}

      {locked && (
        <p className="text-sm text-muted-foreground">Certificates have been sent, so the design is now locked.</p>
      )}
      {upload.isError && <p className="text-sm text-destructive">{errorMessage(upload.error, "Upload failed.")}</p>}
      {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not save.")}</p>}
      {remove.isError && <p className="text-sm text-destructive">{errorMessage(remove.error, "Could not remove.")}</p>}
      {preview.isError && <p className="text-sm text-destructive">{errorMessage(preview.error, "Preview failed.")}</p>}
    </div>
  );
}
