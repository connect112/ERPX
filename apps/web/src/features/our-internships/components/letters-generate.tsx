import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Download, Eye, FileCheck2, History, RefreshCw, Wand2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { BulkDownloadButton } from "@/features/bulk-downloads/components/bulk-download-button";
import { errorMessage, formatBytes } from "@/features/institutions/lib/format";
import {
  type GenerateResult,
  type Letter,
  type LetterSettings,
  type LetterStudent,
  letterKeys,
  lettersApi,
  useLetterStudents,
} from "@/features/our-internships/api/letters-api";
import { DESIGN_TEXT, ROW_STATUS, openBlob, saveBlob } from "@/features/our-internships/lib/letters";

function StatusBadge({ row }: { row: LetterStudent }) {
  const s = ROW_STATUS[row.status];
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <Badge variant={s.variant}>{s.label}</Badge>
      {row.letter?.outdated && <Badge variant="warning">Outdated</Badge>}
    </span>
  );
}

// ------------------------------------------------------------------ Generate

/**
 * Step 3: check who is ready, then make the letters. Students with missing details are listed with what is missing and do not
 * hold up the rest. Pressing Generate again never makes duplicates, and nothing is emailed from here.
 */
export function LettersGenerate({ internshipId, settings, onGo }: { internshipId: string; settings: LetterSettings; onGo: (tab: string) => void }) {
  const queryClient = useQueryClient();
  const students = useLetterStudents(internshipId);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: letterKeys.all(internshipId) });
  const generate = useMutation({
    mutationFn: () => lettersApi.generate(internshipId, {}),
    onSuccess: (r) => {
      setResult(r);
      void refresh();
    },
  });

  if (students.isLoading) return <Skeleton className="h-48 w-full" />;
  if (students.isError || !students.data) return <p className="text-sm text-destructive">Could not load the selected students.</p>;
  const { students: rows, counts, in_progress } = students.data;
  const missing = rows.filter((r) => r.issues.length > 0);
  const toMake = rows.filter((r) => r.issues.length === 0 && (!r.letter || r.letter.status === "failed")).length;
  const made = rows.filter((r) => r.letter && !["pending", "generating"].includes(r.letter.status)).length;
  const total = rows.filter((r) => r.letter).length;
  const blockedBySettings = settings.problems.length > 0 || settings.design_state !== "approved";

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Before you generate</CardTitle>
          <CardDescription>Letters are made from the saved, approved design for every selected student, each with their own details.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={settings.design_state === "approved" ? "success" : "warning"}>{settings.design_state === "approved" ? "Design approved" : "Design not approved"}</Badge>
            <span>{DESIGN_TEXT[settings.design_state]}</span>
            {settings.design_state !== "approved" && (
              <Button size="sm" variant="outline" onClick={() => onGo("preview")}>
                Open the preview
              </Button>
            )}
          </div>
          {settings.problems.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
              <p className="font-medium">Settings still to finish:</p>
              <ul className="list-disc pl-5">
                {settings.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
              <Button size="sm" variant="outline" className="mt-2" onClick={() => onGo("config")}>
                Go to the configuration
              </Button>
            </div>
          )}
          <dl className="flex flex-wrap gap-x-8 gap-y-2">
            {(
              [
                ["Selected students", rows.length],
                ["Missing details", counts.missing_data ?? 0],
                ["Letters made", made],
                ["Failed", counts.failed ?? 0],
              ] as const
            ).map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
                <dd className="text-lg font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      {missing.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
              Fix these before their letters can be made
            </CardTitle>
            <CardDescription>
              Nothing is guessed. Correct the student in the Selected Students tab, or the institution under Institutions, then generate again. The others are not held up.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {missing.map((r) => (
                <li key={r.student_id}>
                  <span className="font-medium">{r.name || r.email || "Unnamed student"}</span>: {r.issues.join(" ")}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Generate the letters</CardTitle>
          <CardDescription>This makes the PDFs only. Reviewing, approving and emailing them are separate steps.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {in_progress > 0 && (
            <div className="space-y-1" role="status" aria-live="polite">
              <div className="flex justify-between text-sm">
                <span>Generating letters...</span>
                <span className="tabular-nums">
                  {total - in_progress} of {total}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded bg-muted">
                <div className="h-full bg-primary transition-all" style={{ width: `${total ? ((total - in_progress) / total) * 100 : 0}%` }} />
              </div>
            </div>
          )}
          {generate.isError && <p className="text-sm text-destructive">{errorMessage(generate.error, "Could not generate the letters.")}</p>}
          {result && <p className="text-sm text-emerald-700 dark:text-emerald-400">{result.message}</p>}
          <div className="flex flex-wrap items-center gap-3">
            <Button disabled={blockedBySettings || toMake === 0 || generate.isPending || in_progress > 0} onClick={() => generate.mutate()}>
              <Wand2 className="h-4 w-4" />
              {generate.isPending ? "Starting..." : toMake === 0 ? "Every letter is made" : `Generate ${toMake} offer letter${toMake === 1 ? "" : "s"}`}
            </Button>
            {made > 0 && (
              <Button variant="outline" onClick={() => onGo("letters")}>
                <FileCheck2 className="h-4 w-4" />
                See the generated letters
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ Generated letters

function VersionsDialog({ internshipId, student, onClose }: { internshipId: string; student: LetterStudent; onClose: () => void }) {
  const list = useQuery({ queryKey: [...letterKeys.all(internshipId), "versions", student.student_id], queryFn: () => lettersApi.versions(internshipId, student.student_id) });
  const versions = list.data;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Versions of {student.name}'s letter</DialogTitle>
          <DialogDescription>Every version is kept, including ones that were sent.</DialogDescription>
        </DialogHeader>
        {list.isError && <p className="text-sm text-destructive">{errorMessage(list.error, "Could not load the versions.")}</p>}
        {list.isLoading && <Skeleton className="h-20 w-full" />}
        <ul className="divide-y text-sm">
          {versions?.map((v) => (
            <li key={v.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                <span className="font-medium">Version {v.version}</span> <span className="text-muted-foreground">{v.reference}</span>
                <br />
                <span className="text-xs text-muted-foreground">{v.generated_at ? new Date(v.generated_at).toLocaleString() : "Not made yet"}</span>
              </span>
              <span className="flex items-center gap-2">
                <Badge variant={ROW_STATUS[v.status].variant}>{ROW_STATUS[v.status].label}</Badge>
                {v.filename && (
                  <Button size="sm" variant="outline" onClick={() => void lettersApi.letterPdf(internshipId, v.id).then((b) => openBlob(b))}>
                    <Eye className="h-3.5 w-3.5" />
                    Open
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}

/** Step 4: every student with their letter. Open or download one, make it again, approve the good ones, or take them all as a ZIP. */
export function LettersList({ internshipId, settings, onGo }: { internshipId: string; settings: LetterSettings; onGo: (tab: string) => void }) {
  const queryClient = useQueryClient();
  const students = useLetterStudents(internshipId);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [versionsOf, setVersionsOf] = useState<LetterStudent | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: letterKeys.all(internshipId) });
  const act = useMutation({
    mutationFn: async (job: () => Promise<string | void>) => job(),
    onSuccess: (m) => {
      setMessage(m ?? null);
      void refresh();
    },
  });

  if (students.isLoading) return <Skeleton className="h-48 w-full" />;
  if (students.isError || !students.data) return <p className="text-sm text-destructive">Could not load the letters.</p>;
  const rows = students.data.students;
  const withLetter = rows.filter((r) => r.letter && r.letter.filename);
  const chosenLetters = withLetter.filter((r) => picked.has(r.student_id)).map((r) => r.letter as Letter);
  const outdated = rows.filter((r) => r.letter?.outdated);
  const readyIds = rows.filter((r) => r.letter?.status === "ready" && !r.letter.outdated).map((r) => (r.letter as Letter).id);
  const allPicked = rows.length > 0 && rows.every((r) => picked.has(r.student_id));
  const toggle = (id: string) =>
    setPicked((p) => {
      const next = new Set(p);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const regenerate = (ids: string[]) =>
    act.mutate(async () => {
      const r = await lettersApi.generate(internshipId, { student_ids: ids, regenerate: true });
      return r.message;
    });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          disabled={act.isPending || (chosenLetters.length === 0 && readyIds.length === 0)}
          onClick={() => {
            const ids = chosenLetters.length ? chosenLetters.filter((l) => l.status === "ready").map((l) => l.id) : readyIds;
            act.mutate(async () => (await lettersApi.approve(internshipId, ids.length ? ids : null)).message);
          }}
        >
          <FileCheck2 className="h-4 w-4" />
          {chosenLetters.length ? "Approve the selected" : "Approve all ready letters"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={act.isPending || withLetter.length === 0}
          onClick={() =>
            act.mutate(async () => {
              saveBlob(await lettersApi.zip(internshipId, chosenLetters.map((l) => l.id)), "OfferLetters.zip");
            })
          }
        >
          <Download className="h-4 w-4" />
          {chosenLetters.length ? `Download ${chosenLetters.length} as ZIP` : "Download all as ZIP"}
        </Button>
        <BulkDownloadButton source="offer_letters" scopeId={internshipId} size="sm" label="Bulk download (custom names)" />
        <Button size="sm" variant="outline" disabled={act.isPending || outdated.length === 0} onClick={() => regenerate(outdated.map((r) => r.student_id))}>
          <RefreshCw className="h-4 w-4" />
          Regenerate {outdated.length || ""} outdated
        </Button>
        {settings.design_state !== "approved" && outdated.length > 0 && <span className="text-xs text-amber-700 dark:text-amber-400">Approve the design again on the preview tab first.</span>}
        <Button size="sm" variant="ghost" onClick={() => onGo("release")}>
          Go to release
        </Button>
      </div>
      {act.isError && <p className="text-sm text-destructive">{errorMessage(act.error, "Could not do that.")}</p>}
      {message && !act.isError && <p className="text-sm text-emerald-700 dark:text-emerald-400">{message}</p>}

      {rows.length === 0 ? (
        <p className="rounded-md border p-8 text-center text-sm text-muted-foreground">No students are selected for this internship yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <input type="checkbox" aria-label="Select every student" checked={allPicked} onChange={() => setPicked(allPicked ? new Set() : new Set(rows.map((r) => r.student_id)))} />
                </TableHead>
                <TableHead>Student</TableHead>
                <TableHead>Institution</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Letter</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.student_id}>
                  <TableCell>
                    <input type="checkbox" aria-label={`Select ${r.name}`} checked={picked.has(r.student_id)} onChange={() => toggle(r.student_id)} />
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">{r.name}</div>
                    <div className="text-xs text-muted-foreground">{r.email}</div>
                  </TableCell>
                  <TableCell>
                    <div>{r.institution}</div>
                    <div className="text-xs text-muted-foreground">{r.location}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge row={r} />
                    {r.status === "missing_data" && <p className="mt-1 max-w-xs text-xs text-muted-foreground">{r.issues.join(" ")}</p>}
                    {r.letter?.error && <p className="mt-1 max-w-xs text-xs text-destructive">{r.letter.error}</p>}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {r.letter ? (
                      <>
                        {r.letter.reference} · v{r.letter.version}
                        {r.letter.pdf_size ? ` · ${r.letter.page_count} pages · ${formatBytes(r.letter.pdf_size)}` : ""}
                      </>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap justify-end gap-1">
                      {r.letter?.filename && (
                        <>
                          <Button size="sm" variant="ghost" onClick={() => void lettersApi.letterPdf(internshipId, (r.letter as Letter).id).then((b) => openBlob(b))}>
                            <Eye className="h-3.5 w-3.5" />
                            Preview
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => void lettersApi.letterPdf(internshipId, (r.letter as Letter).id).then((b) => saveBlob(b, (r.letter as Letter).filename ?? "OfferLetter.pdf"))}>
                            <Download className="h-3.5 w-3.5" />
                            Download
                          </Button>
                        </>
                      )}
                      {r.issues.length === 0 && r.letter && !["pending", "generating"].includes(r.letter.status) && (
                        <Button size="sm" variant="ghost" disabled={act.isPending || settings.design_state !== "approved"} onClick={() => regenerate([r.student_id])}>
                          <RefreshCw className="h-3.5 w-3.5" />
                          Regenerate
                        </Button>
                      )}
                      {r.letter && (
                        <Button size="sm" variant="ghost" aria-label={`Versions of ${r.name}'s letter`} onClick={() => setVersionsOf(r)}>
                          <History className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {versionsOf && <VersionsDialog internshipId={internshipId} student={versionsOf} onClose={() => setVersionsOf(null)} />}
    </div>
  );
}
