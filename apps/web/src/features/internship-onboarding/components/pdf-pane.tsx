import { Download, Loader2, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

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
}

/**
 * Shows a PDF in the page with its page count, zoom and a download button. The file comes from the staff member's own authenticated
 * request and is shown from a temporary object URL that is revoked when the PDF changes or the pane closes.
 */
export function PdfPane({ title, blob, pages, note, filename, loading, error }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [zoom, setZoom] = useState<number>(100);

  useEffect(() => {
    if (!blob) {
      setUrl(null);
      return;
    }
    const made = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
    setUrl(made);
    return () => URL.revokeObjectURL(made);
  }, [blob]);

  const step = (by: 1 | -1) => {
    const i = ZOOM_LEVELS.indexOf(zoom as (typeof ZOOM_LEVELS)[number]);
    const next = ZOOM_LEVELS[Math.min(ZOOM_LEVELS.length - 1, Math.max(0, i + by))];
    setZoom(next);
  };
  const download = () => {
    if (!url) return;
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-medium">{title}</span>
        {pages != null && (
          <span className="text-muted-foreground" data-testid="page-count">
            {pages} page{pages === 1 ? "" : "s"}
          </span>
        )}
        {note && <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">{note}</span>}
        {loading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-label="Drawing the preview" />}
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
          <Button type="button" size="sm" variant="outline" disabled={!url} onClick={download}>
            <Download className="h-4 w-4" />
            Download
          </Button>
        </span>
      </div>
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      <div className="h-[72vh] overflow-auto rounded-md border bg-muted/30">
        {url ? (
          <iframe title={title} src={`${url}#toolbar=0&navpanes=0`} style={{ width: `${zoom}%`, height: `${zoom}%`, minHeight: "100%" }} className="block border-0" />
        ) : (
          !error && <p className="p-6 text-sm text-muted-foreground">{loading ? "Drawing the preview…" : "No preview yet."}</p>
        )}
      </div>
    </div>
  );
}
