import { CheckCircle2, Hourglass } from "lucide-react";

import type { Task } from "@/features/hackathons/api/hackathons-api";
import { ordinal } from "@/features/hackathons/lib/ordinal";

/** A thin bar showing marks earned out of the most a rule (or the task) could give. */
function MarkBar({ earned, max }: { earned: number | null; max: number }) {
  const percent = earned === null || max <= 0 ? 0 : Math.min(100, Math.round((earned / max) * 100));
  return (
    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted" aria-hidden>
      <div className="h-full rounded-full bg-emerald-500" style={{ width: `${percent}%` }} />
    </div>
  );
}

/**
 * What the team gets for a submitted task. Once it has been submitted this shows the
 * rubric as a skeleton (each rule with the most it can earn and a blank mark); once
 * staff have scored it, the same table fills in with the marks, the total, any
 * feedback, and the team's place on the task.
 */
export function TaskResult({ task }: { task: Task }) {
  const submission = task.submission;
  if (!submission) return null;
  const scored = submission.score !== null;
  const rules = task.rubric;
  const maxTotal = rules.length > 0 ? rules.reduce((sum, rule) => sum + rule.points, 0) : task.marks;

  return (
    <div className="space-y-3 rounded-md border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold">{scored ? "Your result" : "How this task will be marked"}</h4>
        {scored ? (
          <span className="flex items-center gap-1.5 text-sm font-semibold text-emerald-700">
            <CheckCircle2 className="h-4 w-4" />
            {submission.score}
            {maxTotal > 0 && ` / ${maxTotal}`}
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Hourglass className="h-3.5 w-3.5" />
            Waiting to be scored
          </span>
        )}
      </div>

      {rules.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted-foreground">
              <th className="pb-1 font-medium">Marked on</th>
              <th className="pb-1 text-right font-medium">Marks</th>
              <th className="w-28 pb-1" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {rules.map((rule) => {
              const earned = scored ? (submission.rubric_scores?.[rule.id] ?? 0) : null;
              return (
                <tr key={rule.id}>
                  <td className="py-2 pr-3">{rule.criterion}</td>
                  <td className="whitespace-nowrap py-2 text-right tabular-nums">
                    <span className={earned === null ? "text-muted-foreground" : "font-semibold"}>
                      {earned === null ? "–" : earned}
                    </span>{" "}
                    <span className="text-muted-foreground">/ {rule.points}</span>
                  </td>
                  <td className="py-2 pl-3">
                    <MarkBar earned={earned} max={rule.points} />
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t">
              <td className="pt-2 font-medium">Total</td>
              <td className="whitespace-nowrap pt-2 text-right font-semibold tabular-nums">
                {scored ? submission.score : "–"} / {maxTotal}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      )}

      {scored && task.task_rank !== null && task.task_teams_scored > 0 && (
        <p className="text-sm">
          Your team's place on this task:{" "}
          <strong>
            {ordinal(task.task_rank)} of {task.task_teams_scored} team{task.task_teams_scored === 1 ? "" : "s"}
          </strong>
        </p>
      )}
      {scored && submission.feedback && (
        <div className="rounded-md bg-muted/50 p-3 text-sm">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Feedback</p>
          <p className="whitespace-pre-wrap">{submission.feedback}</p>
        </div>
      )}
    </div>
  );
}
