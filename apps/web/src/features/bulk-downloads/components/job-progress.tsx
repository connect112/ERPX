import { CheckCircle2, Download, Loader2, XCircle } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  type BulkJob,
  bulkDownloadsApi,
  downloadJob,
  isActive,
  useJobAction,
} from "@/features/bulk-downloads/api/bulk-downloads-api";
import { formatBytes } from "@/features/bulk-downloads/lib/template";
import { errorText } from "@/features/bulk-downloads/lib/errors";

const STATUS_TEXT: Record<BulkJob["status"], string> = {
  queued: "Waiting to start…",
  running: "Preparing the ZIP…",
  completed: "Ready to download",
  failed: "Could not be prepared",
  cancelled: "Cancelled",
  expired: "Expired (the file has been removed)",
};

export function JobProgress({ job }: { job: BulkJob }) {
  const cancel = useJobAction(bulkDownloadsApi.cancel);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const done = job.processed_items + job.failed_items;
  const percent = job.total_items ? Math.round((done / job.total_items) * 100) : 0;
  const active = isActive(job.status);

  const download = async () => {
    setDownloadError(null);
    setDownloading(true);
    try {
      await downloadJob(job.id);
    } catch (error) {
      setDownloadError(errorText(error, "The download could not be started."));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 font-medium">
        {active && <Loader2 className="h-4 w-4 animate-spin" />}
        {job.status === "completed" && <CheckCircle2 className="h-4 w-4 text-emerald-600" />}
        {(job.status === "failed" || job.status === "cancelled") && <XCircle className="h-4 w-4 text-destructive" />}
        {STATUS_TEXT[job.status]}
      </div>

      {(active || job.status === "completed") && (
        <div>
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={job.status === "completed" ? 100 : percent}
          >
            <div className="h-full bg-primary transition-all" style={{ width: `${job.status === "completed" ? 100 : percent}%` }} />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {job.processed_items} of {job.total_items} added
            {job.failed_items > 0 && `, ${job.failed_items} failed`}
            {job.size_bytes ? ` · ${formatBytes(job.size_bytes)}` : ""}
          </p>
        </div>
      )}

      {job.error && <p className="text-sm text-destructive">{job.error}</p>}

      {job.failures.length > 0 && (
        <details className="rounded-md border p-2 text-sm">
          <summary className="cursor-pointer">
            {job.failed_items} document{job.failed_items === 1 ? "" : "s"} could not be added (also listed in the ZIP)
          </summary>
          <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto">
            {job.failures.map((f) => (
              <li key={f.id}>
                <span className="font-medium">{f.title || f.id}</span>: {f.error}
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="flex flex-wrap gap-2">
        {job.status === "completed" && (
          <Button onClick={() => void download()} disabled={downloading}>
            <Download className="h-4 w-4" />
            Download {job.zip_filename}
          </Button>
        )}
        {active && (
          <Button variant="outline" onClick={() => cancel.mutate(job.id)} disabled={cancel.isPending}>
            Cancel
          </Button>
        )}
      </div>
      {downloadError && <p className="text-sm text-destructive">{downloadError}</p>}
      {job.status === "completed" && job.expires_at && (
        <p className="text-xs text-muted-foreground">
          Available until {new Date(job.expires_at).toLocaleString()}. You can also find it under Administration → Bulk
          Downloads.
        </p>
      )}
    </div>
  );
}
