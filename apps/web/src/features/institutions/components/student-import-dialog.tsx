import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { type ImportResult, type ImportSource, institutionsApi, institutionsKeys } from "@/features/institutions/api/institutions-api";
import { errorMessage } from "@/features/institutions/lib/format";

/**
 * Import a student list from an Excel/CSV/text file or pasted text. It is read first and shown back ("what will
 * happen") before anything is saved, so a wrong column or a bad row is seen, not discovered later.
 *
 * With an ``eventId`` the people are registered for that event only; without one they are added to the institution.
 */
export function StudentImportDialog({
  institutionId,
  eventId,
  eventName,
  importer,
  onDone,
  onClose,
}: {
  institutionId: string;
  eventId?: string;
  eventName?: string;
  /** Imports somewhere other than the institution or event endpoints (an internship's own import). */
  importer?: (source: ImportSource, dryRun: boolean) => Promise<ImportResult>;
  /** Called once the list has been saved, to refresh whatever shows the students. */
  onDone?: () => void;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<ImportResult | null>(null);
  const [done, setDone] = useState<ImportResult | null>(null);

  const source = (): ImportSource | null => (mode === "file" ? (file ? { file } : null) : text.trim() ? { text } : null);
  const run = (dryRun: boolean) => {
    const s = source();
    if (!s) throw new Error("Nothing to import.");
    if (importer) return importer(s, dryRun);
    return eventId ? institutionsApi.importEventStudents(eventId, s, dryRun) : institutionsApi.importStudents(institutionId, s, dryRun);
  };

  const check = useMutation({ mutationFn: () => run(true), onSuccess: (r) => setPreview(r) });
  const save = useMutation({
    mutationFn: () => run(false),
    onSuccess: (r) => {
      void queryClient.invalidateQueries({ queryKey: institutionsKeys.all });
      onDone?.();
      setDone(r);
    },
  });

  const changed = () => {
    setPreview(null);
    check.reset();
  };
  const target = eventId ? `registers them for ${eventName ?? "this event"} only` : "adds them to the institution";

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Import students</DialogTitle>
          <DialogDescription>
            Upload an Excel (.xlsx), CSV or text file, or paste the list. Each student needs a name and an email; a phone
            number and any other columns are kept too. The import {target}. People already at the institution are matched by
            email, never duplicated.
          </DialogDescription>
        </DialogHeader>

        {done ? (
          <div className="space-y-3">
            <p className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200">
              Done. {summary(done, !!eventId)}
            </p>
            <ProblemList result={done} />
            <div className="flex justify-end">
              <Button onClick={onClose}>Close</Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex gap-2" role="tablist" aria-label="Where the list comes from">
              {(["file", "text"] as const).map((m) => (
                <Button
                  key={m}
                  type="button"
                  size="sm"
                  role="tab"
                  aria-selected={mode === m}
                  variant={mode === m ? "default" : "outline"}
                  onClick={() => {
                    setMode(m);
                    changed();
                  }}
                >
                  {m === "file" ? "Upload a file" : "Paste text"}
                </Button>
              ))}
            </div>
            {mode === "file" ? (
              <div className="space-y-1">
                <Label htmlFor="import-file">File (.xlsx, .csv or .txt, up to 5 MB)</Label>
                <Input
                  id="import-file"
                  type="file"
                  accept=".xlsx,.xlsm,.csv,.tsv,.txt"
                  onChange={(e) => {
                    setFile(e.target.files?.[0] ?? null);
                    changed();
                  }}
                />
                <p className="text-xs text-muted-foreground">
                  Old .xls files are not supported: save the sheet as .xlsx or CSV first. The first sheet is used.
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                <Label htmlFor="import-text">Student list</Label>
                <Textarea
                  id="import-text"
                  rows={8}
                  placeholder={"Name, Email, Phone\nAsha Rao, asha@example.com, 9876543210\nMeera Iyer, meera@example.com"}
                  value={text}
                  onChange={(e) => {
                    setText(e.target.value);
                    changed();
                  }}
                />
                <p className="text-xs text-muted-foreground">
                  One student per line, separated by commas or tabs, with or without a header row. Pasting from Excel works.
                </p>
              </div>
            )}

            {check.isError && <p className="text-sm text-destructive">{errorMessage(check.error, "Could not read that list.")}</p>}
            {preview && (
              <div className="space-y-2 rounded-md border p-3 text-sm">
                <p className="font-medium">{preview.total_rows} rows read. If you continue:</p>
                <p>{summary(preview, !!eventId)}</p>
                <ProblemList result={preview} />
              </div>
            )}
            {save.isError && <p className="text-sm text-destructive">{errorMessage(save.error, "Could not import the list.")}</p>}

            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              {preview ? (
                <Button disabled={save.isPending || (preview.new_students === 0 && preview.registered === 0)} onClick={() => save.mutate()}>
                  {save.isPending ? "Importing..." : "Import"}
                </Button>
              ) : (
                <Button disabled={!source() || check.isPending} onClick={() => check.mutate()}>
                  {check.isPending ? "Reading..." : "Check the list"}
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function summary(r: ImportResult, forEvent: boolean): string {
  const parts = [`${r.new_students} new student${r.new_students === 1 ? "" : "s"}`];
  if (r.existing_students) parts.push(`${r.existing_students} already at the institution`);
  if (forEvent) {
    parts.push(`${r.registered} registered for the event`);
    if (r.already_registered) parts.push(`${r.already_registered} were already registered`);
    if (r.over_capacity) parts.push(`${r.over_capacity} not added because the event is full`);
  }
  if (r.problems.length) parts.push(`${r.problems.length} row${r.problems.length === 1 ? "" : "s"} skipped`);
  return parts.join(", ") + ".";
}

function ProblemList({ result }: { result: ImportResult }) {
  if (result.problems.length === 0) return null;
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium">Skipped rows</p>
      <ul className="max-h-40 space-y-1 overflow-y-auto text-xs text-muted-foreground">
        {result.problems.slice(0, 100).map((p) => (
          <li key={`${p.row}-${p.reason}`}>
            <span className="font-medium text-foreground">Row {p.row}:</span> {p.reason}
            {p.raw ? <span className="opacity-70"> ({p.raw})</span> : null}
          </li>
        ))}
        {result.problems.length > 100 && <li>…and {result.problems.length - 100} more.</li>}
      </ul>
    </div>
  );
}
