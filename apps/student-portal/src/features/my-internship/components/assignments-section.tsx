import { FileText } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { type MyAssignment, useMyAssignments, useSubmitAssignment } from "@/features/my-internship/api/my-internship-api";
import { checkFiles, errorMessage, formatBytes, formatDateTime, timeLeft } from "@/features/my-internship/lib/format";

function statusOf(a: MyAssignment): { label: string; variant: "success" | "warning" | "info" | "secondary" | "destructive" } {
  const s = a.submission;
  if (s?.reviewed) return { label: "Marked", variant: "success" };
  if (s) return { label: s.is_late ? "Submitted late" : "Submitted", variant: s.is_late ? "warning" : "info" };
  if (a.status === "closed") return { label: "Closed", variant: "secondary" };
  if (!a.can_submit) return { label: "Not open", variant: "secondary" };
  return { label: "To do", variant: "warning" };
}

export function AssignmentsSection({ internshipId }: { internshipId: string }) {
  const { data, isLoading, isError } = useMyAssignments(internshipId);
  const [openId, setOpenId] = useState<string | null>(null);

  if (isLoading) return <Skeleton className="h-32 w-full" />;
  if (isError) return <p className="text-sm text-destructive">Could not load your assignments.</p>;
  if (!data || data.length === 0) {
    return <p className="rounded-md border bg-card p-8 text-center text-sm text-muted-foreground">No assignments have been published yet.</p>;
  }
  const open = data.find((a) => a.id === openId) ?? null;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        {data.map((a) => {
          const status = statusOf(a);
          const left = timeLeft(a.deadline_at);
          return (
            <Card key={a.id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{a.title}</CardTitle>
                  <Badge variant={status.variant}>{status.label}</Badge>
                </div>
                <CardDescription>
                  {a.max_marks} marks
                  {a.deadline_at ? ` · due ${formatDateTime(a.deadline_at)}` : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {!a.submission && left && a.can_submit && <p className="text-sm text-amber-700 dark:text-amber-400">{left} left</p>}
                {a.submission?.reviewed && (
                  <p className="text-sm">
                    Score <strong>{a.submission.score}</strong> / {a.max_marks}
                  </p>
                )}
                <Button variant={a.can_submit && !a.submission ? "default" : "outline"} onClick={() => setOpenId(a.id)}>
                  {a.can_submit && !a.submission ? "Open and submit" : "View"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
      {open && <AssignmentDialog internshipId={internshipId} assignment={open} onClose={() => setOpenId(null)} />}
    </>
  );
}

function FileLink({ file }: { file: { filename: string; size_bytes: number; url: string | null } }) {
  return (
    <a href={file.url ?? "#"} target="_blank" rel="noreferrer" className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted">
      <FileText className="h-4 w-4 shrink-0" />
      <span className="truncate">{file.filename}</span>
      <span className="shrink-0 text-xs text-muted-foreground">{formatBytes(file.size_bytes)}</span>
    </a>
  );
}

function AssignmentDialog({ internshipId, assignment: a, onClose }: { internshipId: string; assignment: MyAssignment; onClose: () => void }) {
  const submit = useSubmitAssignment(internshipId);
  const [note, setNote] = useState(a.submission?.note ?? "");
  const [files, setFiles] = useState<File[]>([]);
  const problem = checkFiles(files, a.max_files);
  const s = a.submission;
  const hasSomething = files.length > 0 || note.trim().length > 0 || !!s?.files.length;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{a.title}</DialogTitle>
          <DialogDescription>
            {a.max_marks} marks{a.deadline_at ? ` · due ${formatDateTime(a.deadline_at)}` : ""}
            {a.allow_late ? " · late submissions are accepted" : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {a.description && <p className="whitespace-pre-wrap text-sm">{a.description}</p>}
          {a.tasks.length > 0 && (
            <ol className="list-decimal space-y-2 pl-5 text-sm">
              {a.tasks.map((t) => (
                <li key={t.id}>
                  <span className="font-medium">{t.title}</span>
                  {t.details && <p className="whitespace-pre-wrap text-muted-foreground">{t.details}</p>}
                </li>
              ))}
            </ol>
          )}
          {a.instructions && (
            <div>
              <h3 className="text-sm font-medium">Instructions</h3>
              <p className="whitespace-pre-wrap text-sm text-muted-foreground">{a.instructions}</p>
            </div>
          )}
          {a.rubric.length > 0 && (
            <div>
              <h3 className="text-sm font-medium">How it is marked</h3>
              <ul className="text-sm text-muted-foreground">
                {a.rubric.map((r) => (
                  <li key={r.id} className="flex justify-between gap-3">
                    <span>{r.criterion}</span>
                    <span>
                      {s?.reviewed && s.rubric_scores ? `${s.rubric_scores[r.id] ?? 0} / ` : ""}
                      {r.points}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {a.files.length > 0 && (
            <div className="space-y-1.5">
              <h3 className="text-sm font-medium">Reference files</h3>
              {a.files.map((f) => (
                <FileLink key={f.id} file={f} />
              ))}
            </div>
          )}

          {s && (
            <div className="space-y-2 rounded-md border bg-muted/30 p-3">
              <h3 className="text-sm font-medium">
                Your submission <span className="font-normal text-muted-foreground">· {formatDateTime(s.submitted_at)}</span>
                {s.is_late && (
                  <Badge variant="warning" className="ml-2">
                    Late
                  </Badge>
                )}
              </h3>
              {s.note && <p className="whitespace-pre-wrap text-sm">{s.note}</p>}
              {s.files.map((f) => (
                <FileLink key={f.id} file={f} />
              ))}
              {s.reviewed && (
                <div className="space-y-1 border-t pt-2">
                  <p className="text-sm">
                    Score <strong>{s.score}</strong> / {a.max_marks}
                  </p>
                  {s.feedback && <p className="whitespace-pre-wrap text-sm text-muted-foreground">{s.feedback}</p>}
                  <p className="text-xs text-muted-foreground">This has been marked, so it can no longer be changed.</p>
                </div>
              )}
            </div>
          )}

          {a.can_submit ? (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (problem || !hasSomething) return;
                submit.mutate({ assignmentId: a.id, note, files }, { onSuccess: onClose });
              }}
            >
              <h3 className="text-sm font-medium">{s ? "Replace your submission" : "Your submission"}</h3>
              <input
                type="file"
                multiple
                aria-label="Files to submit"
                className="block w-full text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1.5 file:text-sm"
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              />
              <p className="text-xs text-muted-foreground">
                Up to {a.max_files} file{a.max_files === 1 ? "" : "s"}, 25 MB each.
                {s && s.files.length > 0 ? " Choosing new files replaces the earlier ones; leave this empty to keep them." : ""}
              </p>
              <Textarea aria-label="Note" rows={3} placeholder="A note for the reviewer (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
              {problem && <p className="text-sm text-destructive">{problem}</p>}
              {submit.isError && <p className="text-sm text-destructive">{errorMessage(submit.error, "Could not submit. Please try again.")}</p>}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={!!problem || !hasSomething || submit.isPending}>
                  {submit.isPending ? "Submitting..." : s ? "Update submission" : "Submit"}
                </Button>
              </div>
            </form>
          ) : (
            !s && (
              <p className="text-sm text-muted-foreground">
                {a.status === "closed" ? "This assignment is closed." : a.starts_at && new Date(a.starts_at) > new Date() ? `Opens ${formatDateTime(a.starts_at)}.` : "The deadline has passed."}
              </p>
            )
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
