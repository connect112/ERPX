import { CheckCircle2, ChevronDown, ChevronRight, Download, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { type Task, hackathonsApi } from "@/features/hackathons/api/hackathons-api";
import { useSubmitTask, useTasks } from "@/features/hackathons/api/hackathons-hooks";

function errorText(error: unknown, fallback: string): string {
  return (
    (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? fallback
  );
}

function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function statusBadge(task: Task) {
  if (!task.submission) return <Badge variant="secondary">Not submitted</Badge>;
  if (task.submission.score !== null) return <Badge variant="success">Scored: {task.submission.score}</Badge>;
  return <Badge variant="info">Submitted</Badge>;
}

/**
 * One task's submission: a report file and a registry / repository URL. Every
 * task has its own form with its own state (the parent keys it by task), so
 * moving to another task never carries the previous task's details over.
 */
function TaskSubmissionForm({
  hackathonId,
  task,
  canSubmit,
}: {
  hackathonId: string;
  task: Task;
  canSubmit: boolean;
}) {
  const saved = task.submission;
  const [repoUrl, setRepoUrl] = useState(saved?.repo_url ?? "");
  const [file, setFile] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const submit = useSubmitTask(hackathonId, task.id);

  const hasSomething = repoUrl.trim() !== "" || file !== null || saved?.report != null;
  const changed = file !== null || repoUrl.trim() !== (saved?.repo_url ?? "");

  return (
    <div className="space-y-4 rounded-md border bg-muted/20 p-4">
      <h4 className="text-sm font-semibold">Task submission</h4>

      <div className="space-y-2">
        <p className="text-sm font-medium leading-none">Task report</p>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.doc,.docx,.ppt,.pptx,.zip"
          className="hidden"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            e.target.value = "";
          }}
        />
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Button type="button" variant="outline" size="sm" disabled={!canSubmit} onClick={() => fileRef.current?.click()}>
            <Upload className="h-4 w-4" />
            {saved?.report || file ? "Replace report" : "Choose report"}
          </Button>
          {file ? (
            <span>
              {file.name} <span className="text-muted-foreground">({formatSize(file.size)}) - not saved yet</span>
            </span>
          ) : saved?.report ? (
            <>
              <span>
                {saved.report.filename}{" "}
                <span className="text-muted-foreground">({formatSize(saved.report.size_bytes)})</span>
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => hackathonsApi.downloadTaskReport(hackathonId, task.id, saved.report?.filename ?? "report")}
              >
                <Download className="h-4 w-4" />
                Download
              </Button>
            </>
          ) : (
            <span className="text-muted-foreground">PDF, Word, PowerPoint or zip, up to 20 MB</span>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor={`url-${task.id}`}>Registry / repository URL</Label>
        <Input
          id={`url-${task.id}`}
          type="url"
          inputMode="url"
          placeholder="https://hub.docker.com/r/your-team/your-image"
          value={repoUrl}
          disabled={!canSubmit}
          onChange={(e) => setRepoUrl(e.target.value)}
        />
      </div>

      {saved && saved.score !== null && (
        <div className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-900">
          <p className="flex items-center gap-1.5 font-medium">
            <CheckCircle2 className="h-4 w-4" />
            Score: {saved.score}
          </p>
          {saved.feedback && <p className="mt-1 whitespace-pre-wrap">{saved.feedback}</p>}
        </div>
      )}

      {!canSubmit ? (
        <p className="text-sm text-muted-foreground">Create or join a team to submit this task.</p>
      ) : (
        <div className="flex flex-wrap items-center gap-3">
          <Button
            disabled={!hasSomething || !changed || submit.isPending}
            onClick={() =>
              submit.mutate(
                { repoUrl: repoUrl.trim(), file },
                {
                  onSuccess: () => {
                    setFile(null);
                  },
                }
              )
            }
          >
            {submit.isPending ? "Saving..." : saved ? "Update submission" : "Submit task"}
          </Button>
          {submit.isSuccess && !changed && <span className="text-sm text-emerald-700">Saved.</span>}
          {saved && <span className="text-xs text-muted-foreground">Last saved {new Date(saved.submitted_at).toLocaleString()}</span>}
        </div>
      )}
      {submit.isError && <p className="text-sm text-destructive">{errorText(submit.error, "Could not save this task.")}</p>}
    </div>
  );
}

/** All of the hackathon's tasks. Open one to read it and submit your team's work for it. */
export function TasksSection({ hackathonId }: { hackathonId: string }) {
  const { data, isLoading } = useTasks(hackathonId);
  const [openId, setOpenId] = useState<string | null>(null);

  if (isLoading || !data) return <Skeleton className="h-40 w-full" />;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Tasks</CardTitle>
        <CardDescription>
          {data.tasks.length === 0
            ? "The organisers haven't published any tasks yet. Check back soon."
            : "Open a task to read it, then submit your team's report and registry / repository URL for it. Each task is submitted separately."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {data.tasks.map((task, index) => {
          const open = openId === task.id;
          return (
            <div key={task.id} className={`rounded-lg border ${open ? "border-primary/50" : ""}`}>
              <button
                type="button"
                className="flex w-full items-center gap-3 p-3 text-left"
                aria-expanded={open}
                onClick={() => setOpenId(open ? null : task.id)}
              >
                {open ? <ChevronDown className="h-4 w-4 shrink-0" /> : <ChevronRight className="h-4 w-4 shrink-0" />}
                <span className="flex-1 font-medium">
                  {index + 1}. {task.title}
                </span>
                {statusBadge(task)}
              </button>
              {open && (
                <div className="space-y-4 border-t p-4">
                  <p className="whitespace-pre-wrap text-sm text-muted-foreground">{task.description}</p>
                  {/* Keyed by task (and by the saved version) so each task has its own form state. */}
                  <TaskSubmissionForm
                    key={`${task.id}:${task.submission?.submitted_at ?? "none"}`}
                    hackathonId={hackathonId}
                    task={task}
                    canSubmit={data.can_submit}
                  />
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
