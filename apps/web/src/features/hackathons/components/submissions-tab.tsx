import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, ExternalLink, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { type TaskSubmissionAdmin, hackathonsApi } from "@/features/hackathons/api/hackathons-api";
import {
  useAiEvaluateAll,
  useAiEvaluateSubmission,
  useDeleteTaskSubmission,
  useGradeTaskSubmission,
  useHackathon,
  useHackathonTeams,
  useTaskSubmissions,
  useUpdateHackathon,
} from "@/features/hackathons/api/hackathons-hooks";

function errorMessage(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error
    ?.message;
  return message ?? fallback;
}

/** The submitted report: a PDF is shown inline, anything else is offered as a download. */
function ReportPreview({ hackathonId, submission }: { hackathonId: string; submission: TaskSubmissionAdmin }) {
  const filename = submission.report_filename;
  const isPdf = filename?.toLowerCase().endsWith(".pdf") ?? false;
  const { data: blob, isLoading } = useQuery({
    queryKey: ["hackathons", hackathonId, "report", submission.id, submission.submitted_at],
    queryFn: () => hackathonsApi.fetchTaskReport(hackathonId, submission.id),
    enabled: Boolean(filename) && isPdf,
    staleTime: Infinity,
  });
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!blob) {
      setUrl(null);
      return;
    }
    const objectUrl = URL.createObjectURL(blob);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [blob]);

  if (!filename) {
    return <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">No report was uploaded.</p>;
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="font-medium">{filename}</span>
        <div className="flex gap-2">
          {url && (
            <Button asChild size="sm" variant="outline">
              <a href={url} target="_blank" rel="noreferrer">
                <ExternalLink className="h-4 w-4" />
                Open in new tab
              </a>
            </Button>
          )}
          <Button size="sm" variant="outline" onClick={() => hackathonsApi.downloadTaskReport(hackathonId, submission.id, filename)}>
            <Download className="h-4 w-4" />
            Download
          </Button>
        </div>
      </div>
      {isPdf ? (
        isLoading || !url ? (
          <Skeleton className="h-96 w-full" />
        ) : (
          <iframe src={url} title={`Report: ${filename}`} className="h-[28rem] w-full rounded-md border bg-background" />
        )
      ) : (
        <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
          This file type can't be previewed here. Use Download to open it.
        </p>
      )}
    </div>
  );
}

/**
 * Marks for one submission, against the task's rubric (or a single score if it has none).
 * Press Enter in a box to save once every box is filled; Enter on an incomplete form jumps to the next empty box.
 */
function ReviewPanel({
  hackathonId,
  submission,
  onSaved,
}: {
  hackathonId: string;
  submission: TaskSubmissionAdmin;
  onSaved: () => void;
}) {
  const remove = useDeleteTaskSubmission(hackathonId);
  const rules = submission.rubric;
  const hasRubric = rules.length > 0;
  const [values, setValues] = useState<Record<string, string>>(() => {
    if (hasRubric) {
      return Object.fromEntries(rules.map((r) => [r.id, submission.rubric_scores?.[r.id]?.toString() ?? ""]));
    }
    return { score: submission.score?.toString() ?? "" };
  });
  const [feedback, setFeedback] = useState(submission.feedback ?? "");
  const inputs = useRef<(HTMLInputElement | null)[]>([]);
  const grade = useGradeTaskSubmission(hackathonId);
  const aiEvaluate = useAiEvaluateSubmission(hackathonId);

  const fields = hasRubric
    ? rules.map((r) => ({ key: r.id, label: r.criterion, max: r.points }))
    : [{ key: "score", label: "Score", max: submission.task_marks || null }];

  const parsed = fields.map((f) => {
    const raw = (values[f.key] ?? "").trim();
    const n = Number(raw);
    return { ...f, raw, n, valid: raw !== "" && Number.isInteger(n) && n >= 0 && (f.max === null || n <= f.max) };
  });
  const allValid = parsed.every((f) => f.valid);
  const total = parsed.reduce((sum, f) => sum + (f.valid ? f.n : 0), 0);
  const maxTotal = hasRubric ? rules.reduce((sum, r) => sum + r.points, 0) : submission.task_marks;

  const save = () => {
    if (!allValid || grade.isPending) return;
    grade.mutate(
      {
        submissionId: submission.id,
        marks: hasRubric
          ? { rubricScores: Object.fromEntries(parsed.map((f) => [f.key, f.n])) }
          : { score: parsed[0].n },
        feedback,
      },
      { onSuccess: onSaved }
    );
  };

  const onEnter = (index: number) => (event: React.KeyboardEvent) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    if (allValid) {
      save();
      return;
    }
    // Not everything is filled in yet: move to the next box that still needs a valid mark.
    const next = parsed.findIndex((f, i) => i > index && !f.valid);
    const target = next >= 0 ? next : parsed.findIndex((f) => !f.valid);
    inputs.current[target]?.focus();
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">{submission.task_title}</h3>
        <p className="text-xs text-muted-foreground">
          Submitted {new Date(submission.submitted_at).toLocaleString()}
          {submission.task_marks > 0 && <> · worth {submission.task_marks} marks</>}
          {submission.resubmission_count > 0 && (
            <>
              {" "}
              · resubmitted {submission.resubmission_count} time{submission.resubmission_count === 1 ? "" : "s"}
            </>
          )}
        </p>
        {submission.score !== null && !submission.reviewed && (
          <p className="mt-2 rounded-md bg-amber-50 p-2 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            The team resubmitted after this was scored. The marks below are for the earlier version; update them to
            review the new one.
          </p>
        )}
      </div>

      <ReportPreview hackathonId={hackathonId} submission={submission} />

      <div className="space-y-2 rounded-md border border-violet-200 bg-violet-50/60 p-3 dark:border-violet-900 dark:bg-violet-950/20">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={aiEvaluate.isPending || !submission.report_filename}
            title={submission.report_filename ? undefined : "There is no report to read"}
            onClick={() => {
              if (
                !submission.reviewed ||
                submission.ai_evaluated_at ||
                window.confirm("This was marked by a person. Evaluate it with AI and replace those marks?")
              ) {
                aiEvaluate.mutate(submission.id);
              }
            }}
          >
            <Sparkles className="h-4 w-4" />
            {aiEvaluate.isPending ? "Reading the report..." : submission.ai_evaluated_at ? "Evaluate again with AI" : "Evaluate with AI"}
          </Button>
          <span className="text-xs text-muted-foreground">
            Reads the report and marks each success criterion. The marks are applied straight away; you can change any of them.
          </span>
        </div>
        {submission.ai_evaluated_at && (
          <p className="text-xs text-violet-900 dark:text-violet-200">
            Marked automatically on {new Date(submission.ai_evaluated_at).toLocaleString()}. Check the reasons below. Saving
            marks yourself replaces the automatic ones.
          </p>
        )}
        {submission.ai_error && !aiEvaluate.isError && (
          <p className="text-xs text-amber-800 dark:text-amber-300">Automatic evaluation: {submission.ai_error}</p>
        )}
        {aiEvaluate.isError && <p className="text-xs text-destructive">{errorMessage(aiEvaluate.error, "Could not evaluate.")}</p>}
      </div>

      <div className="text-sm">
        <span className="font-medium">Registry / repository URL: </span>
        {submission.repo_url ? (
          <a href={submission.repo_url} target="_blank" rel="noreferrer" className="break-all text-primary hover:underline">
            {submission.repo_url}
            <ExternalLink className="ml-1 inline h-3.5 w-3.5" />
          </a>
        ) : (
          <span className="text-muted-foreground">none given</span>
        )}
      </div>

      <div className="space-y-2 rounded-md border p-3">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold">{hasRubric ? "Rubric" : "Score"}</h4>
          <span className="text-sm font-semibold tabular-nums">
            {allValid || parsed.some((f) => f.valid) ? total : 0}
            {maxTotal > 0 && ` / ${maxTotal}`}
          </span>
        </div>
        <div className="space-y-2">
          {parsed.map((f, index) => (
            <div key={f.key} className="flex items-start gap-3">
              <span className="flex-1 text-sm">
                {f.label}
                {submission.ai_reasons?.[f.key] && (
                  <span className="mt-0.5 block text-xs italic text-muted-foreground">{submission.ai_reasons[f.key]}</span>
                )}
              </span>
              <Input
                ref={(el) => {
                  inputs.current[index] = el;
                }}
                type="number"
                min={0}
                max={f.max ?? undefined}
                step={1}
                inputMode="numeric"
                aria-label={`Marks for ${f.label}`}
                className={`w-20 text-right ${f.raw !== "" && !f.valid ? "border-destructive" : ""}`}
                value={values[f.key] ?? ""}
                onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                onKeyDown={onEnter(index)}
              />
              <span className="w-12 text-sm tabular-nums text-muted-foreground">/ {f.max ?? "-"}</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Type the marks and press <kbd className="rounded border px-1">Enter</kbd> to save.
        </p>
      </div>

      <div className="space-y-1">
        <label htmlFor={`fb-${submission.id}`} className="text-sm font-medium">
          Feedback (optional)
        </label>
        <Textarea id={`fb-${submission.id}`} rows={2} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
      </div>

      <div className="flex items-center gap-3">
        <Button disabled={!allValid || grade.isPending} onClick={save}>
          {grade.isPending ? "Saving..." : submission.reviewed ? "Update marks" : "Save marks"}
        </Button>
        {grade.isSuccess && (
          <span className="flex items-center gap-1 text-sm text-emerald-700">
            <CheckCircle2 className="h-4 w-4" /> Saved
          </span>
        )}
        {grade.isError && <span className="text-sm text-destructive">{errorMessage(grade.error, "Could not save the marks.")}</span>}
        <Button
          variant="outline"
          className="ml-auto text-destructive hover:text-destructive"
          disabled={remove.isPending}
          onClick={() => {
            if (
              window.confirm(
                `Delete the submission from team ${submission.team_name} for "${submission.task_title}"? Its report, link and marks are removed and the team can submit this task again.`
              )
            ) {
              remove.mutate(submission.id);
            }
          }}
        >
          <Trash2 className="h-4 w-4" />
          {remove.isPending ? "Deleting..." : "Delete submission"}
        </Button>
      </div>
      {remove.isError && <p className="text-sm text-destructive">{errorMessage(remove.error, "Could not delete it.")}</p>}
    </div>
  );
}

function ReviewDialog({
  hackathonId,
  teamId,
  submissions,
  onClose,
}: {
  hackathonId: string;
  teamId: string;
  submissions: TaskSubmissionAdmin[];
  onClose: () => void;
}) {
  const mine = useMemo(() => submissions.filter((s) => s.team_id === teamId), [submissions, teamId]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = mine.find((s) => s.id === selectedId) ?? mine.find((s) => !s.reviewed) ?? mine[0];
  const reviewed = mine.filter((s) => s.reviewed).length;

  // The team's last submission was deleted: nothing left to show.
  useEffect(() => {
    if (!selected) onClose();
  }, [selected, onClose]);

  if (!selected) return null;
  const next = mine.find((s) => !s.reviewed && s.id !== selected.id);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-6xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{selected.team_name}</DialogTitle>
          <DialogDescription>
            {selected.members.join(", ")} · {mine.length - reviewed} unreviewed, {reviewed} reviewed
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-5 md:grid-cols-[15rem_1fr]">
          <ul className="space-y-1.5">
            {mine.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(s.id)}
                  className={`flex w-full items-start justify-between gap-2 rounded-md border p-2 text-left text-sm ${
                    s.id === selected.id ? "border-primary bg-primary/5" : "hover:bg-muted/50"
                  }`}
                >
                  <span className="min-w-0 flex-1">
                    {s.task_order + 1}. {s.task_title}
                  </span>
                  {s.reviewed ? (
                    <Badge variant="success" className="shrink-0">
                      {s.ai_evaluated_at && "AI "}
                      {s.score}
                      {s.task_marks > 0 && ` / ${s.task_marks}`}
                    </Badge>
                  ) : (
                    <Badge variant="warning" className="shrink-0">
                      {s.score !== null ? "Resubmitted" : "Unreviewed"}
                    </Badge>
                  )}
                </button>
              </li>
            ))}
          </ul>
          {/* Keyed by submission so each one starts from its own saved marks (and keeps its "Saved" note). */}
          <ReviewPanel
            key={`${selected.id}-${selected.ai_evaluated_at ?? ""}`}
            hackathonId={hackathonId}
            submission={selected}
            onSaved={() => next && setSelectedId(next.id)}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Every team's submissions: unreviewed vs reviewed, and a review dialog per team. */
export function SubmissionsTab({ hackathonId }: { hackathonId: string }) {
  const { data: submissions, isLoading } = useTaskSubmissions(hackathonId);
  const { data: teams } = useHackathonTeams(hackathonId);
  const [openTeamId, setOpenTeamId] = useState<string | null>(null);
  const [onlyUnreviewed, setOnlyUnreviewed] = useState(false);
  const { data: hackathon } = useHackathon(hackathonId);
  const updateHackathon = useUpdateHackathon(hackathonId);
  const evaluateAll = useAiEvaluateAll(hackathonId);
  const [evaluatingUntil, setEvaluatingUntil] = useState(0);

  // After starting a bulk evaluation, look for new marks every few seconds for a couple of minutes.
  const queryClient = useQueryClient();
  useEffect(() => {
    if (evaluatingUntil <= Date.now()) return;
    const timer = setInterval(() => {
      void queryClient.invalidateQueries({ queryKey: ["hackathons"] });
      if (Date.now() > evaluatingUntil) clearInterval(timer);
    }, 5000);
    return () => clearInterval(timer);
  }, [evaluatingUntil, queryClient]);

  const rows = useMemo(() => {
    const byTeam = new Map<string, TaskSubmissionAdmin[]>();
    for (const s of submissions ?? []) byTeam.set(s.team_id, [...(byTeam.get(s.team_id) ?? []), s]);
    return (teams ?? [])
      .map((team) => {
        const subs = byTeam.get(team.id) ?? [];
        const reviewed = subs.filter((s) => s.reviewed).length;
        const resubmitted = subs.filter((s) => !s.reviewed && s.score !== null).length;
        return { team, total: subs.length, reviewed, unreviewed: subs.length - reviewed, resubmitted };
      })
      .filter((row) => !onlyUnreviewed || row.unreviewed > 0)
      .sort((a, b) => b.unreviewed - a.unreviewed || a.team.name.localeCompare(b.team.name));
  }, [submissions, teams, onlyUnreviewed]);

  const totalUnreviewed = rows.reduce((sum, r) => sum + r.unreviewed, 0);

  const aiCount = (submissions ?? []).filter((s) => s.ai_evaluated_at).length;
  const readable = (submissions ?? []).filter((s) => s.report_filename).length;

  return (
    <div className="space-y-4">
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-violet-600" />
          Automatic evaluation
        </CardTitle>
        <CardDescription>
          Reads each team's report (PDF, Word or PowerPoint) and marks it against the task's success criteria, with a
          reason for every mark. Marks go straight onto the leaderboard and you can change any of them. {aiCount} of{" "}
          {readable} reports marked automatically so far.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={hackathon?.ai_evaluation_auto ?? true}
            disabled={!hackathon || updateHackathon.isPending}
            onChange={(e) => updateHackathon.mutate({ ai_evaluation_auto: e.target.checked })}
          />
          <span>
            Evaluate every report automatically when a team submits it (marks you gave by hand are never replaced this
            way)
          </span>
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={evaluateAll.isPending}
            onClick={() =>
              evaluateAll.mutate("unreviewed", { onSuccess: () => setEvaluatingUntil(Date.now() + 180_000) })
            }
          >
            Evaluate all unreviewed
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={evaluateAll.isPending}
            onClick={() => {
              if (window.confirm("Evaluate every report again? This replaces all marks, including ones you gave by hand."))
                evaluateAll.mutate("all", { onSuccess: () => setEvaluatingUntil(Date.now() + 180_000) });
            }}
          >
            Re-evaluate everything
          </Button>
          {evaluateAll.isSuccess && <span className="text-sm text-muted-foreground">{evaluateAll.data.message}</span>}
          {evaluateAll.isError && <span className="text-sm text-destructive">{errorMessage(evaluateAll.error, "Could not start.")}</span>}
        </div>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle className="text-base">Submissions by team</CardTitle>
        <CardDescription>
          {totalUnreviewed > 0
            ? `${totalUnreviewed} submission${totalUnreviewed === 1 ? "" : "s"} waiting for review. `
            : "Nothing waiting for review. "}
          Open a team to read its reports and links and mark each submission against the rubric.
        </CardDescription>
        <label className="flex items-center gap-2 pt-1 text-sm">
          <input type="checkbox" checked={onlyUnreviewed} onChange={(e) => setOnlyUnreviewed(e.target.checked)} />
          <span>Show only teams with unreviewed submissions</span>
        </label>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <Skeleton className="m-6 h-24" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Team</TableHead>
                <TableHead>Members</TableHead>
                <TableHead className="text-center">Unreviewed</TableHead>
                <TableHead className="text-center">Reviewed</TableHead>
                <TableHead className="text-right">Points</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(({ team, total, reviewed, unreviewed, resubmitted }) => (
                <TableRow
                  key={team.id}
                  className={total > 0 ? "cursor-pointer" : "opacity-60"}
                  onClick={() => total > 0 && setOpenTeamId(team.id)}
                >
                  <TableCell className="font-medium">
                    {total > 0 ? (
                      <button type="button" className="text-left text-primary hover:underline" onClick={() => setOpenTeamId(team.id)}>
                        {team.name}
                      </button>
                    ) : (
                      team.name
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{team.member_names.join(", ")}</TableCell>
                  <TableCell className="text-center">
                    {total === 0 ? (
                      "-"
                    ) : (
                      <span className="inline-flex items-center gap-1.5">
                        <Badge variant={unreviewed > 0 ? "warning" : "secondary"}>{unreviewed}</Badge>
                        {resubmitted > 0 && (
                          <span className="text-xs text-muted-foreground">({resubmitted} resubmitted)</span>
                        )}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-center">
                    {total === 0 ? "-" : <Badge variant={reviewed > 0 ? "success" : "secondary"}>{reviewed}</Badge>}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{team.total_score}</TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                    {onlyUnreviewed ? "No team has unreviewed submissions." : "No teams yet."}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </CardContent>
      {openTeamId && (
        <ReviewDialog
          hackathonId={hackathonId}
          teamId={openTeamId}
          submissions={submissions ?? []}
          onClose={() => setOpenTeamId(null)}
        />
      )}
    </Card>
    </div>
  );
}
