import { ExternalLink, FileText } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { type MyProject, type SubmissionMethod, useMyProjects, useProjectActions } from "@/features/my-internship/api/my-internship-api";
import { checkFiles, errorMessage, formatBytes, formatDateTime, isWebAddress, timeLeft } from "@/features/my-internship/lib/format";

const METHOD_LABELS: Record<SubmissionMethod, string> = { file: "Upload files", email: "Send by email", repository: "Repository link" };

function allowedMethods(p: MyProject): SubmissionMethod[] {
  return [p.allow_file && "file", p.allow_email && "email", p.allow_repository && "repository"].filter(Boolean) as SubmissionMethod[];
}

function statusOf(p: MyProject): { label: string; variant: "success" | "warning" | "info" | "secondary" } {
  if (p.submission) return { label: p.submission.is_late ? "Handed in late" : "Handed in", variant: p.submission.is_late ? "warning" : "success" };
  if (p.chosen_by_me) return { label: "Your project", variant: "info" };
  if (p.status === "closed") return { label: "Closed", variant: "secondary" };
  if (p.spots_left === 0) return { label: "Full", variant: "secondary" };
  return { label: "Open", variant: "warning" };
}

export function ProjectsSection({ internshipId }: { internshipId: string }) {
  const { data, isLoading, isError } = useMyProjects(internshipId);
  const [openId, setOpenId] = useState<string | null>(null);

  if (isLoading) return <Skeleton className="h-32 w-full" />;
  if (isError) return <p className="text-sm text-destructive">Could not load the projects.</p>;
  if (!data || data.length === 0) {
    return <p className="rounded-md border bg-card p-8 text-center text-sm text-muted-foreground">No projects have been published yet.</p>;
  }
  const mine = data.find((p) => p.chosen_by_me);
  const open = data.find((p) => p.id === openId) ?? null;

  return (
    <>
      <p className="mb-4 text-sm text-muted-foreground">
        {mine ? `You are working on "${mine.title}".` : "Choose one project. You can change your choice until you have handed something in."}
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {data.map((p) => {
          const status = statusOf(p);
          const left = timeLeft(p.deadline_at);
          return (
            <Card key={p.id} className={p.chosen_by_me ? "border-primary" : undefined}>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{p.title}</CardTitle>
                  <Badge variant={status.variant}>{status.label}</Badge>
                </div>
                <CardDescription>
                  {p.deadline_at ? `Due ${formatDateTime(p.deadline_at)}` : "No deadline"}
                  {p.spots_left !== null ? ` · ${p.spots_left} place${p.spots_left === 1 ? "" : "s"} left` : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {p.description && <p className="line-clamp-3 text-sm text-muted-foreground">{p.description}</p>}
                {p.chosen_by_me && !p.submission && left && p.can_submit && <p className="text-sm text-amber-700 dark:text-amber-400">{left} left</p>}
                <Button variant={p.chosen_by_me && !p.submission ? "default" : "outline"} onClick={() => setOpenId(p.id)}>
                  {p.chosen_by_me ? (p.submission ? "View submission" : "Open and submit") : "View details"}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
      {open && <ProjectDialog internshipId={internshipId} project={open} onClose={() => setOpenId(null)} />}
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

function Block({ title, text }: { title: string; text: string | null }) {
  if (!text) return null;
  return (
    <div>
      <h3 className="text-sm font-medium">{title}</h3>
      <p className="whitespace-pre-wrap text-sm text-muted-foreground">{text}</p>
    </div>
  );
}

function ProjectDialog({ internshipId, project: p, onClose }: { internshipId: string; project: MyProject; onClose: () => void }) {
  const actions = useProjectActions(internshipId);
  const methods = allowedMethods(p);
  const s = p.submission;
  const [method, setMethod] = useState<SubmissionMethod>(s?.method ?? methods[0] ?? "file");
  const [files, setFiles] = useState<File[]>([]);
  const [repo, setRepo] = useState(s?.repository_url ?? "");
  const [note, setNote] = useState(s?.note ?? "");

  const fileProblem = method === "file" ? checkFiles(files, p.max_files) : null;
  const ready =
    method === "file"
      ? (files.length > 0 || (s?.method === "file" && s.files.length > 0)) && !fileProblem
      : method === "repository"
        ? isWebAddress(repo)
        : note.trim().length > 0;
  const error = actions.choose.error ?? actions.drop.error ?? actions.submit.error;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{p.title}</DialogTitle>
          <DialogDescription>
            {p.deadline_at ? `Due ${formatDateTime(p.deadline_at)}` : "No deadline"}
            {p.allow_late ? " · late submissions are accepted" : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Block title="About the project" text={p.description} />
          <Block title="Objectives" text={p.objectives} />
          <Block title="Rules" text={p.rules} />
          {p.reference_links.length > 0 && (
            <div className="space-y-1">
              <h3 className="text-sm font-medium">Reference links</h3>
              {p.reference_links.map((l) => (
                <a key={l.id} href={l.url} target="_blank" rel="noreferrer noopener" className="flex items-center gap-1.5 text-sm text-primary hover:underline">
                  <ExternalLink className="h-3.5 w-3.5 shrink-0" />
                  {l.title}
                </a>
              ))}
            </div>
          )}
          {p.documents.length > 0 && (
            <div className="space-y-1.5">
              <h3 className="text-sm font-medium">Project documents</h3>
              {p.documents.map((f) => (
                <FileLink key={f.id} file={f} />
              ))}
            </div>
          )}
          {p.templates.length > 0 && (
            <div className="space-y-1.5">
              <h3 className="text-sm font-medium">Templates</h3>
              {p.templates.map((f) => (
                <FileLink key={f.id} file={f} />
              ))}
            </div>
          )}

          {!p.chosen_by_me && (
            <div className="space-y-2 border-t pt-3">
              {p.can_choose ? (
                <Button disabled={actions.choose.isPending} onClick={() => actions.choose.mutate(p.id)}>
                  {actions.choose.isPending ? "Choosing..." : "Choose this project"}
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">
                  {p.status === "closed" ? "This project is closed." : p.spots_left === 0 ? "This project is full." : "You can no longer switch projects because you have handed in your work."}
                </p>
              )}
              {p.can_choose && <p className="text-xs text-muted-foreground">You can change your choice until you have handed something in.</p>}
            </div>
          )}

          {p.chosen_by_me && s && (
            <div className="space-y-2 rounded-md border bg-muted/30 p-3">
              <h3 className="text-sm font-medium">
                Your submission <span className="font-normal text-muted-foreground">· {formatDateTime(s.submitted_at)}</span>
                {s.is_late && (
                  <Badge variant="warning" className="ml-2">
                    Late
                  </Badge>
                )}
              </h3>
              <p className="text-sm">{METHOD_LABELS[s.method]}</p>
              {s.repository_url && (
                <a href={s.repository_url} target="_blank" rel="noreferrer noopener" className="break-all text-sm text-primary hover:underline">
                  {s.repository_url}
                </a>
              )}
              {s.note && <p className="whitespace-pre-wrap text-sm text-muted-foreground">{s.note}</p>}
              {s.files.map((f) => (
                <FileLink key={f.id} file={f} />
              ))}
              {s.method === "email" && (
                <p className="text-xs text-muted-foreground">{s.received_at ? `Your email was received on ${formatDateTime(s.received_at)}.` : "Waiting for us to confirm that your email arrived."}</p>
              )}
            </div>
          )}

          {p.chosen_by_me && p.can_submit && (
            <form
              className="space-y-3 border-t pt-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (!ready) return;
                actions.submit.mutate({ projectId: p.id, method, repositoryUrl: repo, note, files }, { onSuccess: onClose });
              }}
            >
              <h3 className="text-sm font-medium">{s ? "Replace your submission" : "Hand in your project"}</h3>
              <Block title="" text={p.submission_instructions} />
              {methods.length > 1 && (
                <div className="flex flex-wrap gap-4" role="radiogroup" aria-label="How to hand in">
                  {methods.map((m) => (
                    <label key={m} className="flex items-center gap-2 text-sm">
                      <input type="radio" name="method" checked={method === m} onChange={() => setMethod(m)} />
                      {METHOD_LABELS[m]}
                    </label>
                  ))}
                </div>
              )}
              {method === "file" && (
                <>
                  <input
                    type="file"
                    multiple
                    aria-label="Files to submit"
                    className="block w-full text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1.5 file:text-sm"
                    onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
                  />
                  <p className="text-xs text-muted-foreground">
                    Up to {p.max_files} file{p.max_files === 1 ? "" : "s"}, 25 MB each.
                    {s?.method === "file" && s.files.length > 0 ? " Choosing new files replaces the earlier ones; leave this empty to keep them." : ""}
                  </p>
                  {fileProblem && <p className="text-sm text-destructive">{fileProblem}</p>}
                </>
              )}
              {method === "repository" && (
                <div className="space-y-1">
                  <Input aria-label="Repository link" type="url" placeholder="https://github.com/you/project" value={repo} onChange={(e) => setRepo(e.target.value)} />
                  {repo && !isWebAddress(repo) && <p className="text-sm text-destructive">Enter a full web address starting with http:// or https://</p>}
                </div>
              )}
              {method === "email" && (
                <p className="rounded-md border bg-card p-3 text-sm">
                  Email your work to <strong>{p.submission_email}</strong>, then write below when and from which address you sent it.
                </p>
              )}
              <Textarea
                aria-label="Note"
                rows={3}
                placeholder={method === "email" ? "Sent from asha@example.com on 12 Nov, 10:30" : "A note for the reviewer (optional)"}
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              {error && <p className="text-sm text-destructive">{errorMessage(error, "That did not work. Please try again.")}</p>}
              <div className="flex flex-wrap justify-between gap-2">
                {!s ? (
                  <Button type="button" variant="ghost" disabled={actions.drop.isPending} onClick={() => actions.drop.mutate(undefined, { onSuccess: onClose })}>
                    Choose a different project
                  </Button>
                ) : (
                  <span />
                )}
                <div className="flex gap-2">
                  <Button type="button" variant="outline" onClick={onClose}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={!ready || actions.submit.isPending}>
                    {actions.submit.isPending ? "Submitting..." : s ? "Update submission" : "Submit"}
                  </Button>
                </div>
              </div>
            </form>
          )}
          {p.chosen_by_me && !p.can_submit && !s && (
            <p className="text-sm text-muted-foreground">
              {p.status === "closed" ? "This project is closed." : p.starts_at && new Date(p.starts_at) > new Date() ? `Submissions open ${formatDateTime(p.starts_at)}.` : "The deadline has passed."}
            </p>
          )}
          {error && !p.can_submit && <p className="text-sm text-destructive">{errorMessage(error, "That did not work. Please try again.")}</p>}
        </div>
      </DialogContent>
    </Dialog>
  );
}
