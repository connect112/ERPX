import { Download, Loader2, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { type RenderedPdf, renderPdf } from "@/features/internship-onboarding/lib/pdf-render";

export const ZOOM_LEVELS = [60, 80, 100, 125, 150, 200] as const;

interface Props {
  title: string;
  /** The PDF to show; null while there is none yet. */
  blob: Blob | null;
  pages?: number | null;
  /** A short note about the file, e.g. that it is a sample. */
  note?: string | null;
  filename: string;
  loading?: boolean;
  error?: string | null;
  /** From 1024px, fill the height of the column it sits in (instead of a fixed height) and scroll inside it. */
  fill?: boolean;
}

/**
 * Shows a PDF in the page with its page count, zoom and a download button. The pages are drawn on canvases (see ``renderPdf``): nothing in
 * here takes focus or scrolls the page, the pane keeps a fixed height so the layout around it never changes size, and a new preview
 * replaces the old one only once it is ready, keeping the pane's own scroll position.
 */
export function PdfPane({ title, blob, pages, note, filename, loading, error, fill }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState<number>(100);
  const [drawn, setDrawn] = useState<number | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [width, setWidth] = useState(0);

  // redraw when the phone is turned or the pane is resized by a useful amount (not for every pixel)
  useEffect(() => {
    const el = host.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const watcher = new ResizeObserver(() => setWidth((w) => (Math.abs(el.clientWidth - w) > 24 ? el.clientWidth : w)));
    watcher.observe(el);
    return () => watcher.disconnect();
  }, []);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    if (!blob) {
      el.replaceChildren();
      setDrawn(null);
      return;
    }
    const abort = new AbortController();
    let made: RenderedPdf | null = null;
    renderPdf(blob, el, { zoom, signal: abort.signal })
      .then((r) => {
        made = r;
        setDrawn(r.pages);
        setProblem(null);
      })
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name === "AbortError") return; // replaced by a newer preview: not a failure
        console.error("The PDF could not be drawn", e); // the real reason stays visible to whoever opens the console
        const reason = (e instanceof Error ? e.message : String(e)).replace(/\s+/g, " ").slice(0, 140);
        setProblem(`The preview could not be shown here${reason ? ` (${reason})` : ""}. You can still download it.`);
      });
    return () => {
      abort.abort();
      made?.destroy();
    };
  }, [blob, zoom, width]);

  const step = (by: 1 | -1) => {
    const i = ZOOM_LEVELS.indexOf(zoom as (typeof ZOOM_LEVELS)[number]);
    setZoom(ZOOM_LEVELS[Math.min(ZOOM_LEVELS.length - 1, Math.max(0, i + by))]);
  };
  const download = () => {
    if (!blob) return;
    const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const count = drawn ?? pages ?? null;
  return (
    <div className={`space-y-2 ${fill ? "lg:flex lg:min-h-0 lg:flex-1 lg:flex-col lg:space-y-0 lg:gap-2" : ""}`}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">{title}</span>
        {count != null && (
          <span className="text-muted-foreground" data-testid="page-count">
            {count} page{count === 1 ? "" : "s"}
          </span>
        )}
        {note && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">{note}</span>}
        <Loader2 className={`h-4 w-4 animate-spin text-muted-foreground ${loading ? "" : "invisible"}`} aria-label={loading ? "Drawing the preview" : undefined} aria-hidden={!loading} />
        <span className="ml-auto flex items-center gap-1">
          <Button type="button" size="sm" variant="outline" aria-label="Zoom out" disabled={zoom === ZOOM_LEVELS[0]} onClick={() => step(-1)}>
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="w-12 text-center text-xs tabular-nums" aria-live="polite">
            {zoom}%
          </span>
          <Button type="button" size="sm" variant="outline" aria-label="Zoom in" disabled={zoom === ZOOM_LEVELS[ZOOM_LEVELS.length - 1]} onClick={() => step(1)}>
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button type="button" size="sm" variant="outline" disabled={!blob} onClick={download}>
            <Download className="h-4 w-4" />
            Download
          </Button>
        </span>
      </div>
      {(error || problem) && (
        <p className="text-sm text-destructive" role="alert">
          {error ?? problem}
        </p>
      )}
      {/* a fixed-size pane: whatever happens inside it, the page around it keeps its size and position */}
      <div className={`relative h-[72vh] min-h-[22rem] overflow-hidden rounded-md border bg-muted/30 ${fill ? "lg:h-auto lg:min-h-0 lg:flex-1" : ""}`}>
        <div ref={host} className="absolute inset-0 overflow-auto p-3" data-testid="pdf-pages" />
        {!blob && !error && (
          <p className="pointer-events-none absolute inset-0 grid place-items-center p-6 text-sm text-muted-foreground">{loading ? "Drawing the preview…" : "No preview yet."}</p>
        )}
      </div>
    </div>
  );
}
