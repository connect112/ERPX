import { Download, Trash2 } from "lucide-react";
import { Fragment, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  type BulkJob,
  bulkDownloadsApi,
  downloadJob,
  isActive,
  useBulkJobs,
  useJobAction,
} from "@/features/bulk-downloads/api/bulk-downloads-api";
import { JobProgress } from "@/features/bulk-downloads/components/job-progress";
import { errorText } from "@/features/bulk-downloads/lib/errors";
import { formatBytes } from "@/features/bulk-downloads/lib/template";

const BADGE: Record<BulkJob["status"], { label: string; variant: "secondary" | "info" | "success" | "destructive" | "outline" }> = {
  queued: { label: "Waiting", variant: "info" },
  running: { label: "Preparing", variant: "info" },
  completed: { label: "Ready", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "secondary" },
  expired: { label: "Expired", variant: "outline" },
};

export function BulkDownloadsPage() {
  const { data: jobs, isLoading } = useBulkJobs();
  const discard = useJobAction(bulkDownloadsApi.discard);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const download = async (id: string) => {
    setError(null);
    try {
      await downloadJob(id);
    } catch (e) {
      setError(errorText(e, "The download could not be started."));
    }
  };

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Bulk Downloads</h1>
        <p className="mt-1 text-muted-foreground">
          The ZIPs you asked for. Start a new one with “Bulk download” on an exam, internship, payroll run or documents
          list. Each ZIP is kept for a limited time and then removed; only you can see and download your own.
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Documents</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Files</TableHead>
                <TableHead>Requested</TableHead>
                <TableHead>Available until</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(jobs ?? []).map((job) => (
                <Fragment key={job.id}>
                  <TableRow>
                    <TableCell>
                      <div className="font-medium">{job.source_label}</div>
                      <div className="text-xs text-muted-foreground">
                        {job.scope_label}
                        {job.zip_filename && ` · ${job.zip_filename}`}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={BADGE[job.status].variant}>{BADGE[job.status].label}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">
                      {isActive(job.status) ? `${job.processed_items}/${job.total_items}` : job.processed_items}
                      {job.failed_items > 0 && <span className="text-destructive"> · {job.failed_items} failed</span>}
                      {job.size_bytes ? <div className="text-xs text-muted-foreground">{formatBytes(job.size_bytes)}</div> : null}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{new Date(job.created_at).toLocaleString()}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {job.status === "completed" && job.expires_at ? new Date(job.expires_at).toLocaleString() : "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-right">
                      {job.status === "completed" && (
                        <Button size="sm" variant="ghost" aria-label="Download" onClick={() => void download(job.id)}>
                          <Download className="h-4 w-4" />
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => setOpen(open === job.id ? null : job.id)}>
                        {open === job.id ? "Hide" : "Details"}
                      </Button>
                      {job.status === "completed" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label="Remove the file now"
                          title="Remove the file now"
                          disabled={discard.isPending}
                          onClick={() => discard.mutate(job.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                  {open === job.id && (
                    <TableRow>
                      <TableCell colSpan={6} className="bg-muted/30">
                        <JobProgress job={job} />
                        <p className="mt-3 font-mono text-xs text-muted-foreground">
                          File names: {job.options.filename_template}
                          {job.options.folder_template ? ` · folders: ${job.options.folder_template}` : ""}
                        </p>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              ))}
              {!isLoading && (jobs ?? []).length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                    No bulk downloads yet.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
