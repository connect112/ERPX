import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  type CertificateLayout,
  DEFAULT_CERTIFICATE_LAYOUT,
  type NameAdjust,
  type ReviewItem,
  type WorkshopExam,
  workshopExamsApi,
} from "@/features/workshop-exams/api/workshop-exams-api";
import "@/features/workshop-exams/components/certificate-fonts.css";
import { baselineOffset, FONT_CSS, measureText, SCRIPT_FONTS } from "@/features/workshop-exams/lib/certificate-render";

const NO_FIX: NameAdjust = { size: 1, dx: 0, dy: 0 };
const LONG_NAME = 26;

function errorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: { error?: { message?: string; details?: { msg?: string }[] } } } })
    ?.response?.data?.error;
  const detail = Array.isArray(data?.details) ? data?.details[0]?.msg : undefined;
  return (detail ? detail.replace(/^Value error,\s*/, "") : data?.message) ?? fallback;
}

const sameFix = (a: NameAdjust, b: NameAdjust) => a.size === b.size && a.dx === b.dx && a.dy === b.dy;

function openPdf(blob: Blob) {
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function StatusBadge({ item }: { item: ReviewItem }) {
  if (item.certificate_sent_at)
    return <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">Sent</span>;
  if (item.certificate_verified_at)
    return <span className="rounded bg-sky-100 px-1.5 py-0.5 text-xs text-sky-800 dark:bg-sky-950 dark:text-sky-200">Verified</span>;
  return <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">Not verified</span>;
}

/** One person's certificate on the design, with their name drawn the way the PDF will draw it. */
function CertificatePreview({
  imageUrl,
  layout,
  name,
  number,
  fix,
  fontsReady,
}: {
  imageUrl: string;
  layout: CertificateLayout;
  name: string;
  number: string | null;
  fix: NameAdjust;
  fontsReady: number;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const update = () => setBox({ width: el.clientWidth, height: el.clientHeight });
    const observer = new ResizeObserver(update);
    observer.observe(el);
    update();
    return () => observer.disconnect();
  }, [imageUrl]);

  const shown = useMemo(() => {
    void fontsReady;
    let size = layout.font_size * box.height;
    const limit = layout.max_width * box.width;
    const floor = size * 0.4;
    let metrics = measureText(name, layout.font, size);
    if (metrics.width > limit && metrics.width > 0) {
      size = Math.max(floor, (size * limit) / metrics.width);
    }
    size *= fix.size; // the fix comes after the automatic fit, like in the PDF
    metrics = measureText(name, layout.font, size);
    const idSize = layout.id_font_size * box.height;
    const idMetrics = measureText(number ?? "", layout.id_font, idSize);
    return {
      size,
      top: (layout.name_y + fix.dy) * box.height - baselineOffset(size, metrics.ascent, metrics.descent),
      idSize,
      idTop: layout.id_y * box.height - baselineOffset(idSize, idMetrics.ascent, idMetrics.descent),
    };
  }, [layout, box, name, number, fix, fontsReady]);

  const font = FONT_CSS[layout.font];
  const idFont = FONT_CSS[layout.id_font];
  const gradient = layout.color_end && layout.color_end.toLowerCase() !== layout.color.toLowerCase();

  return (
    <div ref={boxRef} className="relative select-none overflow-hidden rounded-md border">
      <img src={imageUrl} alt="Certificate design" className="block w-full" draggable={false} />
      <span
        className="pointer-events-none absolute whitespace-nowrap"
        style={{
          left: `${(layout.name_x + fix.dx) * 100}%`,
          top: `${shown.top}px`,
          transform: "translateX(-50%)",
          fontSize: `${shown.size}px`,
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
        }}
      >
        {name}
      </span>
      {layout.show_id && number && (
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
          }}
        >
          {number}
        </span>
      )}
    </div>
  );
}

/** Check, fix and send one person's certificate. Remounted for each person so its drafts start fresh. */
function ReviewDetail({
  exam,
  item,
  imageUrl,
  layout,
  fontsReady,
  onChanged,
}: {
  exam: WorkshopExam;
  item: ReviewItem;
  imageUrl: string | null;
  layout: CertificateLayout;
  fontsReady: number;
  onChanged: () => void;
}) {
  const [name, setName] = useState(item.name);
  const [email, setEmail] = useState(item.email);
  const [fix, setFix] = useState<NameAdjust>(item.certificate_adjust ?? NO_FIX);
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const nameChanged = name.trim().replace(/\s+/g, " ") !== item.name;
  const fixChanged = !sameFix(fix, item.certificate_adjust ?? NO_FIX);
  const emailChanged = email.trim().toLowerCase() !== item.email;
  const designDirty = nameChanged || fixChanged;

  const fail = (error: unknown, fallback: string) => setNotice({ tone: "error", text: errorMessage(error, fallback) });

  const saveDesign = async (thenVerify: boolean) => {
    setNotice(null);
    try {
      if (nameChanged) await workshopExamsApi.updateAttendee(exam.id, item.id, { name: name.trim() });
      if (fixChanged) await workshopExamsApi.adjustCertificate(exam.id, item.id, sameFix(fix, NO_FIX) ? null : fix);
      if (thenVerify) await workshopExamsApi.verifyCertificate(exam.id, item.id, true);
      setNotice({ tone: "ok", text: thenVerify ? "Saved and marked as verified." : "Saved. It needs verifying again." });
      onChanged();
    } catch (error) {
      fail(error, "Could not save.");
    }
  };

  const verify = useMutation({
    mutationFn: (verified: boolean) => workshopExamsApi.verifyCertificate(exam.id, item.id, verified),
    onSuccess: onChanged,
    onError: (error) => fail(error, "Could not change that."),
  });
  const saveEmail = useMutation({
    mutationFn: () => workshopExamsApi.updateAttendee(exam.id, item.id, { email: email.trim() }),
    onSuccess: () => {
      setNotice({ tone: "ok", text: "Email address saved. Nothing was sent - use the Send button when you are ready." });
      onChanged();
    },
    onError: (error) => fail(error, "Could not save the email address."),
  });
  const send = useMutation({
    mutationFn: () => workshopExamsApi.sendCertificate(exam.id, item.id),
    onSuccess: (result) => {
      setNotice({ tone: "ok", text: result.message });
      onChanged();
    },
    onError: (error) => fail(error, "Could not send."),
  });
  const pdf = useMutation({
    mutationFn: () => workshopExamsApi.attendeeCertificatePdf(exam.id, item.id),
    onSuccess: openPdf,
    onError: (error) => fail(error, "Could not open the PDF."),
  });

  const verified = item.certificate_verified_at !== null;
  const slider = (id: string, label: string, min: number, max: number, step: number, value: number, set: (v: number) => void, show: string) => (
    <div className="space-y-1">
      <Label htmlFor={id} className="flex justify-between text-xs">
        <span>{label}</span>
        <span className="text-muted-foreground">{show}</span>
      </Label>
      <input id={id} type="range" min={min} max={max} step={step} value={value} className="w-full" onChange={(e) => set(Number(e.target.value))} />
    </div>
  );

  return (
    <div className="space-y-4">
      {exam.has_certificate_template ? (
        imageUrl ? (
          <CertificatePreview imageUrl={imageUrl} layout={layout} name={name || " "} number={item.certificate_number} fix={fix} fontsReady={fontsReady} />
        ) : (
          <div className="flex h-40 items-center justify-center rounded-md border text-sm text-muted-foreground">Loading design...</div>
        )
      ) : (
        <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
          This exam uses the automatic certificate, so there is no picture to show here. Use "Open exact PDF" to see it.
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1 sm:col-span-2">
          <Label htmlFor="rv-name">Name on the certificate</Label>
          <Input id="rv-name" value={name} maxLength={255} onChange={(e) => setName(e.target.value)} />
        </div>
        {exam.has_certificate_template && (
          <>
            {slider("rv-size", "Name size", 30, 150, 1, Math.round(fix.size * 100), (v) => setFix((f) => ({ ...f, size: v / 100 })), `${Math.round(fix.size * 100)}%`)}
            {slider("rv-dx", "Move left / right", -20, 20, 0.5, fix.dx * 100, (v) => setFix((f) => ({ ...f, dx: v / 100 })), `${(fix.dx * 100).toFixed(1)}%`)}
            {slider("rv-dy", "Move up / down", -10, 10, 0.25, fix.dy * 100, (v) => setFix((f) => ({ ...f, dy: v / 100 })), `${(fix.dy * 100).toFixed(1)}%`)}
            <div className="flex items-end">
              <Button type="button" variant="ghost" size="sm" disabled={sameFix(fix, NO_FIX)} onClick={() => setFix(NO_FIX)}>
                Reset size and position
              </Button>
            </div>
          </>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button disabled={!designDirty || !name.trim()} variant="outline" onClick={() => void saveDesign(false)}>
          Save changes
        </Button>
        <Button disabled={(verified && !designDirty) || !name.trim()} onClick={() => void saveDesign(true)}>
          {designDirty ? "Save and mark verified" : "Mark as verified"}
        </Button>
        {verified && !designDirty && (
          <Button variant="ghost" disabled={verify.isPending} onClick={() => verify.mutate(false)}>
            Undo verified
          </Button>
        )}
        <Button variant="outline" disabled={pdf.isPending || designDirty} title={designDirty ? "Save your changes first" : undefined} onClick={() => pdf.mutate()}>
          Open exact PDF
        </Button>
      </div>

      <div className="space-y-2 rounded-md border p-3">
        <Label htmlFor="rv-email">Email address</Label>
        <div className="flex gap-2">
          <Input id="rv-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <Button variant="outline" disabled={!emailChanged || !email.includes("@") || saveEmail.isPending} onClick={() => saveEmail.mutate()}>
            Save email
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Changing the address never sends anything by itself. Wrong address? Fix it, then send this one certificate.
        </p>
        <Button
          variant="outline"
          disabled={send.isPending || emailChanged || designDirty}
          title={emailChanged || designDirty ? "Save your changes first" : undefined}
          onClick={() => {
            const again = item.certificate_sent_at !== null;
            if (window.confirm(`${again ? "Send this certificate again" : "Send this certificate"} to ${item.email}?`)) send.mutate();
          }}
        >
          {item.certificate_sent_at ? `Send again to ${item.email}` : `Send now to ${item.email}`}
        </Button>
      </div>

      {notice && <p className={notice.tone === "ok" ? "text-sm text-emerald-700 dark:text-emerald-400" : "text-sm text-destructive"}>{notice.text}</p>}
    </div>
  );
}

/**
 * Optional step: look through every certificate before it is emailed, fix long or badly placed names on the spot,
 * mark each verified, and fix a wrong email address. Skippable with "Verify everyone".
 */
export function CertificateReviewDialog({ exam, onClose }: { exam: WorkshopExam; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [fontsReady, setFontsReady] = useState(0);
  const [summary, setSummary] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const layout: CertificateLayout = exam.certificate_layout ?? DEFAULT_CERTIFICATE_LAYOUT;

  const review = useQuery({
    queryKey: ["workshop-exams", exam.id, "review"],
    queryFn: () => workshopExamsApi.openCertificateReview(exam.id),
  });
  const items = useMemo(() => review.data?.items ?? [], [review.data]);
  const required = exam.certificate_review;
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["workshop-exams"] });

  useEffect(() => {
    if (!exam.has_certificate_template) return;
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
  }, [exam.id, exam.has_certificate_template]);

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

  const setRequired = useMutation({
    mutationFn: (value: boolean) => workshopExamsApi.update(exam.id, { certificate_review: value }),
    onSuccess: refresh,
  });
  const verifyAll = useMutation({
    mutationFn: () => workshopExamsApi.verifyAllCertificates(exam.id),
    onSuccess: (result) => {
      setSummary({ tone: "ok", text: result.message });
      void refresh();
    },
    onError: (error) => setSummary({ tone: "error", text: errorMessage(error, "Could not verify.") }),
  });
  const sendAll = useMutation({
    mutationFn: () => workshopExamsApi.sendCertificatesNow(exam.id, false),
    onSuccess: (result) => {
      setSummary({ tone: "ok", text: result.message });
      void refresh();
    },
    onError: (error) => setSummary({ tone: "error", text: errorMessage(error, "Could not send the certificates.") }),
  });

  const verifiedCount = items.filter((i) => i.certificate_verified_at || i.certificate_sent_at).length;
  const visible = onlyOpen ? items.filter((i) => !i.certificate_verified_at && !i.certificate_sent_at) : items;
  const selected = items.find((i) => i.id === selectedId) ?? null;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle>Review certificates</DialogTitle>
          <DialogDescription>
            Look at each certificate before it is sent. Fix a long name by making it smaller or moving it, correct an
            email address, and mark it verified. This step is optional.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md border p-3 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={required}
              disabled={setRequired.isPending || !!exam.certificates_dispatched_at}
              onChange={(e) => setRequired.mutate(e.target.checked)}
            />
            <span>Don't send until every certificate is verified</span>
          </label>
          <span className="text-muted-foreground">
            {verifiedCount} of {items.length} verified
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={verifyAll.isPending || verifiedCount === items.length}
            onClick={() => {
              if (window.confirm("Mark every certificate as verified without checking them one by one?")) verifyAll.mutate();
            }}
          >
            Verify everyone (skip review)
          </Button>
          <Button
            size="sm"
            disabled={sendAll.isPending || items.length === 0}
            onClick={() => {
              if (window.confirm("Send every certificate now? This also closes the exam.")) sendAll.mutate();
            }}
          >
            Send all certificates
          </Button>
        </div>
        {summary && <p className={summary.tone === "ok" ? "text-sm text-emerald-700 dark:text-emerald-400" : "text-sm text-destructive"}>{summary.text}</p>}

        {review.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nobody has a certificate yet. People appear here once they have submitted the exam, or were added from a hackathon.</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-[18rem_1fr]">
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
                Only those not verified yet
              </label>
              <ul className="max-h-[60vh] space-y-1 overflow-y-auto pr-1">
                {visible.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(item.id)}
                      className={`w-full rounded-md border p-2 text-left text-sm hover:bg-muted ${selectedId === item.id ? "border-primary bg-muted" : ""}`}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium">{item.name}</span>
                        <StatusBadge item={item} />
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">{item.email}</span>
                      {item.name.length > LONG_NAME && <span className="text-xs text-amber-700 dark:text-amber-400">Long name - check it fits</span>}
                    </button>
                  </li>
                ))}
                {visible.length === 0 && <li className="p-2 text-sm text-muted-foreground">Everyone is verified.</li>}
              </ul>
            </div>
            <div>
              {selected ? (
                <ReviewDetail
                  key={selected.id}
                  exam={exam}
                  item={selected}
                  imageUrl={imageUrl}
                  layout={layout}
                  fontsReady={fontsReady}
                  onChanged={() => void refresh()}
                />
              ) : (
                <p className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">Pick a person on the left to see their certificate.</p>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
