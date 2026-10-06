import { Download, Upload } from "lucide-react";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type ReportInfo, hackathonsApi } from "@/features/hackathons/api/hackathons-api";
import { useUploadReport } from "@/features/hackathons/api/hackathons-hooks";

const ACCEPT = ".pdf,.doc,.docx,.ppt,.pptx,.zip";
const MAX_MB = 20;

function errorText(error: unknown, fallback: string): string {
  return (
    (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? fallback
  );
}

function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** The team's written report. Any member can upload or replace it. */
export function ReportCard({ hackathonId, report }: { hackathonId: string; report: ReportInfo | null }) {
  const upload = useUploadReport(hackathonId);
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Project report</CardTitle>
        <CardDescription>
          Upload your team's report as a PDF, Word, PowerPoint or zip file (up to {MAX_MB} MB). Uploading again
          replaces the previous file.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <input
          ref={fileRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate(file);
            e.target.value = "";
          }}
        />
        {report ? (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
            <div>
              <p className="font-medium">{report.filename}</p>
              <p className="text-xs text-muted-foreground">
                {formatSize(report.size_bytes)} · uploaded {new Date(report.uploaded_at).toLocaleString()}
              </p>
            </div>
            <Button size="sm" variant="outline" onClick={() => hackathonsApi.downloadReport(hackathonId, report.filename)}>
              <Download className="h-4 w-4" />
              Download
            </Button>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No report uploaded yet.</p>
        )}
        <Button disabled={upload.isPending} onClick={() => fileRef.current?.click()}>
          <Upload className="h-4 w-4" />
          {upload.isPending ? "Uploading..." : report ? "Replace report" : "Upload report"}
        </Button>
        {upload.isSuccess && <p className="text-sm text-emerald-700">Report uploaded.</p>}
        {upload.isError && <p className="text-sm text-destructive">{errorText(upload.error, "Upload failed.")}</p>}
      </CardContent>
    </Card>
  );
}
