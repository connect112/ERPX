import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  type BulkSource,
  type NamingOptions,
  bulkDownloadsApi,
  useBulkJob,
  useSourceInfo,
} from "@/features/bulk-downloads/api/bulk-downloads-api";
import { type ChooseFilters, ChooseStep } from "@/features/bulk-downloads/components/choose-step";
import { JobProgress } from "@/features/bulk-downloads/components/job-progress";
import { NamingStep } from "@/features/bulk-downloads/components/naming-step";
import { errorText } from "@/features/bulk-downloads/lib/errors";
import { type Selection, emptySelection, toPayload } from "@/features/bulk-downloads/lib/selection";

type Step = "choose" | "name" | "progress";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  source: BulkSource;
  /** The exam, internship or payroll run the documents belong to (null for organization-wide sources). */
  scopeId: string | null;
}

/**
 * Bulk download in three steps: choose the documents (across pages, or "all matching"), choose how the files and the
 * ZIP are named (with a live preview from the server), then follow the progress and download.
 */
export function BulkDownloadDialog({ open, onOpenChange, source, scopeId }: Props) {
  const info = useSourceInfo(source, scopeId, open);
  const [step, setStep] = useState<Step>("choose");
  const [filters, setFilters] = useState<ChooseFilters>({ search: "", status: "", page: 1 });
  const [selection, setSelection] = useState<Selection>(emptySelection());
  const [options, setOptions] = useState<NamingOptions | null>(null);
  const [namingValid, setNamingValid] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useBulkJob(jobId);

  useEffect(() => {
    if (info.data && options === null) {
      setOptions({
        filename_template: info.data.presets[0]?.template ?? "{{document_type}}_{{index}}",
        folder_template: "",
        zip_template: info.data.default_zip_template,
      });
    }
  }, [info.data, options]);

  const start = useMutation({
    mutationFn: () =>
      bulkDownloadsApi.create(
        source,
        scopeId,
        toPayload(selection, { search: filters.search, status: filters.status }),
        options as NamingOptions
      ),
    onSuccess: (created) => {
      setJobId(created.id);
      setStep("progress");
    },
  });

  const reset = () => {
    setStep("choose");
    setSelection(emptySelection());
    setFilters({ search: "", status: "", page: 1 });
    setJobId(null);
    start.reset();
  };
  const close = (next: boolean) => {
    onOpenChange(next);
    if (!next) reset();
  };

  // "All matching" is counted against the list on screen; the server resolves and checks the real set anyway.
  const canContinue = selection.mode === "all" || selection.ids.size > 0;

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle>Bulk download: {info.data?.label ?? "documents"}</DialogTitle>
          <DialogDescription>
            {info.data?.scope_label}
            {step === "choose" && " · Choose the documents. Your choice is kept as you move between pages."}
            {step === "name" && " · Choose how the files and the ZIP are named."}
          </DialogDescription>
        </DialogHeader>

        {info.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {info.isError && <p className="text-sm text-destructive">{errorText(info.error, "This download is not available to you.")}</p>}

        {info.data && step === "choose" && (
          <ChooseStep
            source={source}
            scopeId={scopeId}
            info={info.data}
            filters={filters}
            onFilters={setFilters}
            selection={selection}
            onSelection={setSelection}
          />
        )}
        {info.data && options && step === "name" && (
          <NamingStep
            source={source}
            scopeId={scopeId}
            info={info.data}
            selection={toPayload(selection, { search: filters.search, status: filters.status })}
            options={options}
            onOptions={setOptions}
            onValidity={setNamingValid}
          />
        )}
        {step === "progress" && job.data && <JobProgress job={job.data} />}

        {start.isError && <p className="text-sm text-destructive">{errorText(start.error, "The download could not be started.")}</p>}

        <DialogFooter className="gap-2">
          {step === "choose" && (
            <Button disabled={!info.data || !canContinue} onClick={() => setStep("name")}>
              Next: file names
            </Button>
          )}
          {step === "name" && (
            <>
              <Button variant="outline" onClick={() => setStep("choose")}>
                Back
              </Button>
              <Button disabled={!namingValid || start.isPending} onClick={() => start.mutate()}>
                {start.isPending ? "Starting…" : "Prepare ZIP"}
              </Button>
            </>
          )}
          {step === "progress" && (
            <>
              <Button variant="outline" onClick={reset}>
                New download
              </Button>
              <Button variant="outline" onClick={() => close(false)}>
                Close
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
