import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Send, Trash2, Upload } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { errorMessage, formatBytes } from "@/features/institutions/lib/format";
import { offerKeys, offersApi, ourInternshipsKeys } from "@/features/our-internships/api/our-internships-api";
import { OfferDesigner } from "@/features/our-internships/components/offer-designer";
import { OfferEmailCard } from "@/features/our-internships/components/offer-email-card";
import { useCanDelete } from "@/features/our-internships/lib/internship-access";

/**
 * Everything about the offers in one place, top to bottom in the order it is done: the letter, where details go on it, the
 * email, then release. Release sends each selected student their own letter in the background; the Selected tab shows how
 * each one went.
 */
export function OffersTab({ internshipId }: { internshipId: string }) {
  const canDelete = useCanDelete();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const settings = useQuery({
    queryKey: offerKeys.settings(internshipId),
    queryFn: () => offersApi.settings(internshipId),
    // while letters are going out, keep the counts moving
    refetchInterval: (query) => ((query.state.data?.counts.queued ?? 0) > 0 ? 4000 : false),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ourInternshipsKeys.all });
  const store = (next: Awaited<ReturnType<typeof offersApi.settings>>) => queryClient.setQueryData(offerKeys.settings(internshipId), next);

  const upload = useMutation({
    mutationFn: (f: File) => offersApi.uploadTemplate(internshipId, f),
    onSuccess: (next) => {
      store(next);
      setFile(null);
    },
  });
  const remove = useMutation({ mutationFn: () => offersApi.removeTemplate(internshipId), onSuccess: store });
  const release = useMutation({
    mutationFn: () => offersApi.release(internshipId),
    onSuccess: () => {
      void refresh();
    },
  });

  if (settings.isLoading) return <Skeleton className="h-48 w-full" />;
  if (settings.isError || !settings.data) return <p className="text-sm text-destructive">Could not load the offer settings.</p>;
  const s = settings.data;
  const toSend = s.counts.not_sent + s.counts.failed;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">1. The offer letter</CardTitle>
          <CardDescription>
            Upload your internship offer letter as a PDF, finished except for the student's details. Everything on it (wording,
            letterhead, signature) is kept exactly as it is.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {s.has_template && (
            <div className="flex items-center justify-between gap-3 rounded-md border p-3 text-sm">
              <span className="flex items-center gap-2">
                <FileText className="h-4 w-4" aria-hidden="true" />
                {s.template_filename} <span className="text-muted-foreground">({s.template_pages} page{s.template_pages === 1 ? "" : "s"}, {formatBytes(s.template_size)})</span>
              </span>
              {canDelete && (
              <Button
                variant="ghost"
                size="sm"
                disabled={remove.isPending}
                onClick={() => {
                  if (window.confirm("Remove this letter? The positions you set on it are removed too.")) remove.mutate();
                }}
              >
                <Trash2 className="h-4 w-4" />
                Remove
              </Button>
              )}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <Input aria-label="Offer letter PDF" type="file" accept="application/pdf,.pdf" className="max-w-sm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <Button type="button" disabled={!file || upload.isPending} onClick={() => file && upload.mutate(file)}>
              <Upload className="h-4 w-4" />
              {upload.isPending ? "Uploading..." : s.has_template ? "Replace the letter" : "Upload"}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">PDF only, up to 10 MB and 10 pages, not password protected.</p>
          {(upload.isError || remove.isError) && <p className="text-sm text-destructive">{errorMessage(upload.error ?? remove.error, "Could not do that.")}</p>}
        </CardContent>
      </Card>

      {s.has_template && <OfferDesigner internshipId={internshipId} settings={s} />}
      <OfferEmailCard internshipId={internshipId} settings={s} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Release the offers</CardTitle>
          <CardDescription>
            Generates a letter for each selected student from the template and emails it to their registered address. You can
            preview any student's letter from the Selected tab first.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
            {(
              [
                ["Selected", s.counts.selected],
                ["Sent", s.counts.sent],
                ["Sending", s.counts.queued],
                ["Not sent yet", s.counts.not_sent],
                ["Failed", s.counts.failed],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
                <dd className="text-lg font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          {s.missing.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-sm text-amber-700 dark:text-amber-400">
              {s.missing.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          )}
          {s.counts.failed > 0 && <p className="text-sm text-destructive">{s.counts.failed} offer{s.counts.failed === 1 ? "" : "s"} could not be sent. Open the Selected tab for the reason; Release sends them again.</p>}
          {release.isError && <p className="text-sm text-destructive">{errorMessage(release.error, "Could not release the offers.")}</p>}
          {release.isSuccess && <p className="text-sm text-emerald-700 dark:text-emerald-400">{release.data.message}</p>}
          <Button
            disabled={s.missing.length > 0 || toSend === 0 || release.isPending}
            onClick={() => {
              if (window.confirm(`Send an offer letter by email to ${toSend} student${toSend === 1 ? "" : "s"}? This cannot be undone.`)) release.mutate();
            }}
          >
            <Send className="h-4 w-4" />
            {release.isPending ? "Releasing..." : toSend === 0 && s.counts.selected > 0 ? "All offers released" : `Release ${toSend || ""} offer letter${toSend === 1 ? "" : "s"}`.replace("  ", " ")}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
