import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type CertificateFont,
  type CertificateLayout,
  DEFAULT_CERTIFICATE_LAYOUT,
  type WorkshopExam,
  workshopExamsApi,
} from "@/features/workshop-exams/api/workshop-exams-api";

const SAMPLE_NAME = "Sample Student Name";

const FONT_CSS: Record<CertificateFont, { family: string; style: string }> = {
  sans_bold: { family: "Helvetica, Arial, sans-serif", style: "normal" },
  serif_bold: { family: "'Times New Roman', Times, serif", style: "normal" },
  serif_bold_italic: { family: "'Times New Roman', Times, serif", style: "italic" },
};

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

const clamp01 = (n: number) => Math.min(1, Math.max(0, n));

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
  const [boxHeight, setBoxHeight] = useState(0);
  const [testEmail, setTestEmail] = useState("");
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

  // Name size is a fraction of the page height, so track the preview's height.
  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    const observer = new ResizeObserver(() => setBoxHeight(box.clientHeight));
    observer.observe(box);
    setBoxHeight(box.clientHeight);
    return () => observer.disconnect();
  }, [imageUrl]);

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
  const preview = useMutation({
    mutationFn: () => workshopExamsApi.certificatePreviewPdf(exam.id, layout),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    },
  });
  const sendTest = useMutation({
    mutationFn: () => workshopExamsApi.emailTestCertificate(exam.id, testEmail.trim(), layout),
  });

  const place = useCallback((event: React.PointerEvent | PointerEvent) => {
    const box = boxRef.current;
    if (!box) return;
    const rect = box.getBoundingClientRect();
    setLayout((l) => ({
      ...l,
      name_x: clamp01((event.clientX - rect.left) / rect.width),
      name_y: clamp01((event.clientY - rect.top) / rect.height),
    }));
  }, []);

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
    setLayout((l) => ({ ...l, name_x: clamp01(l.name_x + move[0]), name_y: clamp01(l.name_y + move[1]) }));
  };

  const set = <K extends keyof CertificateLayout>(key: K, value: CertificateLayout[K]) =>
    setLayout((l) => ({ ...l, [key]: value }));

  const dirty = JSON.stringify(layout) !== JSON.stringify(exam.certificate_layout ?? DEFAULT_CERTIFICATE_LAYOUT);
  const font = FONT_CSS[layout.font];

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
            Click or drag on the certificate to place the name (arrow keys nudge it). The text shown is only a
            sample - use "Preview PDF" to see exactly what students get.
          </p>

          <div
            ref={boxRef}
            tabIndex={0}
            role="slider"
            aria-label="Position of the student's name on the certificate"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(layout.name_x * 100)}
            aria-valuetext={`${Math.round(layout.name_x * 100)}% from the left, ${Math.round(layout.name_y * 100)}% from the top`}
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
                  className="pointer-events-none absolute whitespace-nowrap leading-none"
                  style={{
                    left: `${layout.name_x * 100}%`,
                    top: `${layout.name_y * 100}%`,
                    transform: "translate(-50%, -85%)",
                    fontSize: `${layout.font_size * boxHeight}px`,
                    fontFamily: font.family,
                    fontStyle: font.style,
                    fontWeight: 700,
                    color: layout.color,
                    maxWidth: `${layout.max_width * 100}%`,
                    overflow: "hidden",
                    outline: "1px dashed rgba(37, 99, 235, 0.7)",
                    outlineOffset: "2px",
                  }}
                >
                  {SAMPLE_NAME}
                </span>
                <span
                  className="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-600 ring-2 ring-white"
                  style={{ left: `${layout.name_x * 100}%`, top: `${layout.name_y * 100}%` }}
                />
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
                <option value="sans_bold">Sans-serif bold</option>
                <option value="serif_bold">Serif bold</option>
                <option value="serif_bold_italic">Serif bold italic</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="cd-color">Text colour</Label>
              <input
                id="cd-color"
                type="color"
                className="h-9 w-full rounded-md border bg-background p-1"
                disabled={locked}
                value={layout.color}
                onChange={(e) => set("color", e.target.value)}
              />
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
