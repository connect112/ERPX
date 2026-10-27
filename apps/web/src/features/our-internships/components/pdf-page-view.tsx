import { type ReactNode, useEffect, useRef, useState } from "react";

import { fractionFromClick } from "@/features/our-internships/lib/offer-layout";

interface PdfPageViewProps {
  /** The PDF's bytes. */
  data: ArrayBuffer;
  /** 1-based page number. */
  page: number;
  /** Width the page is drawn at, in CSS pixels. */
  width: number;
  /** Called with where the page was clicked, as fractions of its width and height. */
  onPick?: (x: number, y: number) => void;
  /** Arrow keys on the focused page: move by this much, as fractions of the page (Shift for a bigger step). */
  onNudge?: (dx: number, dy: number) => void;
  /** Drawn on top of the page, positioned inside a box exactly the size of the page. */
  children?: (size: { width: number; height: number }) => ReactNode;
}

/**
 * One page of a PDF drawn in the browser, so a position can be chosen by clicking it. PDF.js is loaded only when a page is
 * actually shown (it is large), and its worker is bundled with the app rather than fetched from anywhere else.
 */
export function PdfPageView({ data, page, width, onPick, onNudge, children }: PdfPageViewProps) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let task: { destroy: () => Promise<void> } | null = null;
    (async () => {
      try {
        const [pdfjs, worker] = await Promise.all([import("pdfjs-dist"), import("pdfjs-dist/build/pdf.worker.min.mjs?url")]);
        pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
        // getDocument takes ownership of the bytes it is given, so it gets its own copy
        const loading = pdfjs.getDocument({ data: new Uint8Array(data.slice(0)) });
        task = loading;
        const doc = await loading.promise;
        const pdfPage = await doc.getPage(page);
        if (cancelled) return;
        const base = pdfPage.getViewport({ scale: 1 });
        const scale = width / base.width;
        const ratio = window.devicePixelRatio || 1;
        const viewport = pdfPage.getViewport({ scale: scale * ratio });
        const el = canvas.current;
        if (!el) return;
        el.width = Math.floor(viewport.width);
        el.height = Math.floor(viewport.height);
        const context = el.getContext("2d");
        if (!context) throw new Error("no canvas");
        await pdfPage.render({ canvasContext: context, viewport }).promise;
        if (!cancelled) {
          setSize({ width, height: Math.round((base.height * scale) as number) });
          setError(null);
        }
      } catch {
        if (!cancelled) setError("The letter could not be displayed.");
      }
    })();
    return () => {
      cancelled = true;
      void task?.destroy();
    };
  }, [data, page, width]);

  if (error) return <p className="text-sm text-destructive">{error}</p>;
  return (
    <div
      ref={box}
      className="relative select-none overflow-hidden rounded border bg-white shadow-sm focus-visible:ring-2 focus-visible:ring-ring"
      style={{ width, height: size?.height ?? Math.round(width * 1.414), cursor: onPick ? "crosshair" : undefined }}
      role={onPick ? "button" : undefined}
      tabIndex={onPick ? 0 : undefined}
      aria-label={onPick ? `Letter page ${page}. Click to place the selected detail, or use the arrow keys to move it.` : undefined}
      onKeyDown={(e) => {
        if (!onNudge) return;
        const step = e.shiftKey ? 0.02 : 0.004;
        const moves: Record<string, [number, number]> = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
        const move = moves[e.key];
        if (!move) return;
        e.preventDefault();
        onNudge(move[0], move[1]);
      }}
      onClick={(e) => {
        if (!onPick || !box.current) return;
        const { x, y } = fractionFromClick(box.current.getBoundingClientRect(), e.clientX, e.clientY);
        onPick(x, y);
      }}
    >
      <canvas ref={canvas} style={{ width: "100%", height: "100%", display: "block" }} aria-label={`Letter, page ${page}`} />
      {size && children?.(size)}
      {!size && <div className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">Loading the letter...</div>}
    </div>
  );
}
