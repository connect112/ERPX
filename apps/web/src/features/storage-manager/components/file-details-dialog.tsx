import { Download, Lock, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { type FileItem, type PreviewResponse, storageApi } from "@/features/storage-manager/api/storage-api";
import { useAnalysis } from "@/features/storage-manager/api/storage-hooks";
import { StatusBadge } from "@/features/storage-manager/components/status-badge";
import { formatBytes, formatDate, VERDICT_LABELS } from "@/features/storage-manager/lib/format";

interface Props {
  item: FileItem | null;
  canDelete: boolean;
  onClose: () => void;
  onDelete: (item: FileItem) => void;
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-2 py-1 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words">{value}</dd>
    </div>
  );
}

/** Shows the file safely: a short-lived link for storage files, an authenticated blob for database files. */
function Preview({ item }: { item: FileItem }) {
  const [state, setState] = useState<{ preview: PreviewResponse; src: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!item.previewable) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    setState(null);
    setError(null);
    storageApi
      .preview(item.id)
      .then(async (preview) => {
        let src = preview.url;
        if (preview.mode === "content" && preview.url) {
          objectUrl = URL.createObjectURL(await storageApi.content(preview.url));
          src = objectUrl;
        }
        if (!cancelled) setState({ preview, src });
      })
      .catch(() => !cancelled && setError("The preview could not be loaded."));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [item.id, item.previewable]);

  if (!item.previewable) {
    return <p className="text-sm text-muted-foreground">This file type cannot be previewed here. Use Download.</p>;
  }
  if (error) return <p className="text-sm text-destructive">{error}</p>;
  if (!state) return <Skeleton className="h-64 w-full" />;
  if (!state.src) return <p className="text-sm text-muted-foreground">{state.preview.message ?? "No preview available."}</p>;

  switch (state.preview.kind) {
    case "image":
      return <img src={state.src} alt={item.name} className="max-h-96 w-full rounded-md border object-contain" />;
    case "video":
      // eslint-disable-next-line jsx-a11y/media-has-caption -- an administrator inspecting an uploaded file; it has no caption track
      return <video src={state.src} controls className="max-h-96 w-full rounded-md border" />;
    case "pdf":
      // Chrome refuses to show a PDF inside a sandboxed frame. The type was checked on the server, and the browser's
      // own PDF viewer is isolated from this page, so a plain frame is used for PDFs only.
      return <iframe title={item.name} src={state.src} referrerPolicy="no-referrer" className="h-96 w-full rounded-md border bg-white" />;
    case "text":
      // sandbox: the frame can show the text but cannot run scripts or reach this page
      return <iframe title={item.name} src={state.src} sandbox="" className="h-96 w-full rounded-md border bg-white" />;
    default:
      return <p className="text-sm text-muted-foreground">No preview available.</p>;
  }
}

async function download(item: FileItem): Promise<void> {
  const preview = await storageApi.preview(item.id, true);
  if (!preview.url) return;
  let href = preview.url;
  let revoke: string | null = null;
  if (preview.mode === "content") {
    revoke = URL.createObjectURL(await storageApi.content(preview.url));
    href = revoke;
  }
  const link = document.createElement("a");
  link.href = href;
  link.download = item.name;
  link.rel = "noopener";
  link.click();
  if (revoke) setTimeout(() => URL.revokeObjectURL(revoke as string), 10_000);
}

export function FileDetailsDialog({ item, canDelete, onClose, onDelete }: Props) {
  const analysis = useAnalysis(item?.id ?? null);
  const [downloading, setDownloading] = useState(false);

  return (
    <Dialog open={item !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        {item && (
          <>
            <DialogHeader>
              <DialogTitle className="flex flex-wrap items-center gap-2 break-all">
                {item.name} <StatusBadge status={item.status} />
                {item.protected && (
                  <Badge variant="outline" className="gap-1">
                    <Lock className="h-3 w-3" /> Protected
                  </Badge>
                )}
              </DialogTitle>
              <DialogDescription>{item.source_label}</DialogDescription>
            </DialogHeader>

            <Preview item={item} />

            <dl className="divide-y rounded-md border px-3">
              <Row label="Size" value={formatBytes(item.size_bytes)} />
              <Row label="Type" value={item.content_type ?? "unknown"} />
              <Row label="Location" value={<code className="text-xs">{item.location}</code>} />
              <Row label="Module" value={item.module} />
              <Row label="Owner" value={item.owner ?? "—"} />
              <Row label="Organization" value={item.organization_name ?? "Not attributed to an organization"} />
              <Row label="Created" value={formatDate(item.created_at)} />
            </dl>

            <section aria-label="Dependency check" className="space-y-2">
              <h3 className="text-sm font-semibold">Is it still needed?</h3>
              {analysis.isLoading && <Skeleton className="h-16 w-full" />}
              {analysis.isError && <p className="text-sm text-destructive">The dependency check failed.</p>}
              {analysis.data && (
                <div className="space-y-2 rounded-md border p-3 text-sm">
                  <p className="font-medium">{VERDICT_LABELS[analysis.data.verdict] ?? analysis.data.verdict}</p>
                  {analysis.data.reasons.map((reason) => (
                    <p key={reason} className="text-muted-foreground">
                      {reason}
                    </p>
                  ))}
                  <ul className="list-disc space-y-1 pl-5">
                    {analysis.data.evidence.map((evidence, index) => (
                      <li key={index}>{evidence.text}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>

            <div className="flex flex-wrap justify-end gap-2">
              <Button
                variant="outline"
                disabled={downloading}
                onClick={() => {
                  setDownloading(true);
                  download(item).finally(() => setDownloading(false));
                }}
              >
                <Download className="h-4 w-4" /> Download
              </Button>
              {canDelete && (
                <Button
                  variant="destructive"
                  disabled={!analysis.data?.can_delete}
                  title={analysis.data?.can_delete ? undefined : "This file is not eligible for deletion"}
                  onClick={() => onDelete(item)}
                >
                  <Trash2 className="h-4 w-4" /> Move to Trash
                </Button>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
