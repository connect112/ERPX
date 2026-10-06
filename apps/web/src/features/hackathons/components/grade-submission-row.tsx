import { Download } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { type TaskSubmissionAdmin, hackathonsApi } from "@/features/hackathons/api/hackathons-api";
import { useGradeTaskSubmission } from "@/features/hackathons/api/hackathons-hooks";

/** One team's submission for one task, with the score and feedback to award for it. */
export function GradeSubmissionRow({
  hackathonId,
  submission,
}: {
  hackathonId: string;
  submission: TaskSubmissionAdmin;
}) {
  const [score, setScore] = useState(submission.score?.toString() ?? "");
  const [feedback, setFeedback] = useState(submission.feedback ?? "");
  const scoreId = useId();
  const feedbackId = useId();
  const grade = useGradeTaskSubmission(hackathonId);

  const parsed = Number(score);
  const valid = score.trim() !== "" && Number.isInteger(parsed) && parsed >= 0;
  const unchanged = valid && parsed === submission.score && feedback === (submission.feedback ?? "");

  return (
    <div className="space-y-3 border-t py-4 first:border-t-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">{submission.team_name}</p>
        <p className="text-xs text-muted-foreground">
          {submission.members.join(", ")} &middot; Submitted {new Date(submission.submitted_at).toLocaleString()}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        {submission.repo_url ? (
          <a href={submission.repo_url} target="_blank" rel="noreferrer" className="break-all text-primary hover:underline">
            {submission.repo_url}
          </a>
        ) : (
          <span className="text-muted-foreground">No URL</span>
        )}
        {submission.report_filename ? (
          <button
            type="button"
            className="inline-flex items-center gap-1 text-primary hover:underline"
            onClick={() => hackathonsApi.downloadTaskReport(hackathonId, submission.id, submission.report_filename as string)}
          >
            <Download className="h-3.5 w-3.5" />
            {submission.report_filename}
          </button>
        ) : (
          <span className="text-muted-foreground">No report</span>
        )}
      </div>

      <div className="flex items-end gap-3">
        <div className="w-24 space-y-1">
          <label htmlFor={scoreId} className="text-xs font-medium text-muted-foreground">
            Score
          </label>
          <Input id={scoreId} type="number" min={0} step={1} value={score} onChange={(e) => setScore(e.target.value)} />
        </div>
        <div className="flex-1 space-y-1">
          <label htmlFor={feedbackId} className="text-xs font-medium text-muted-foreground">
            Feedback
          </label>
          <Textarea
            id={feedbackId}
            rows={1}
            className="min-h-0"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
          />
        </div>
        <Button
          size="sm"
          disabled={!valid || unchanged || grade.isPending}
          onClick={() => grade.mutate({ submissionId: submission.id, score: parsed, feedback })}
        >
          {grade.isPending ? "Saving..." : submission.score === null ? "Award score" : "Update score"}
        </Button>
      </div>
      {grade.isSuccess && unchanged && <p className="text-xs text-emerald-700">Saved - the leaderboard is updated.</p>}
      {grade.isError && <p className="text-xs text-destructive">Could not save the score.</p>}
    </div>
  );
}
