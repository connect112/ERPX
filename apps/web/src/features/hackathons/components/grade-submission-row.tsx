import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useGradeSubmission } from "@/features/hackathons/api/hackathons-hooks";
import type { SubmissionPublic, TeamPublic } from "@/features/hackathons/api/hackathons-api";

interface GradeSubmissionRowProps {
  hackathonId: string;
  submission: SubmissionPublic;
  team: TeamPublic | undefined;
}

export function GradeSubmissionRow({ hackathonId, submission, team }: GradeSubmissionRowProps) {
  const [score, setScore] = useState(submission.score?.toString() ?? "");
  const [feedback, setFeedback] = useState(submission.feedback ?? "");
  const gradeMutation = useGradeSubmission(hackathonId);

  const handleGrade = () => {
    const parsedScore = Number(score);
    if (Number.isNaN(parsedScore) || parsedScore < 0) return;
    gradeMutation.mutate({ submissionId: submission.id, score: parsedScore, feedback });
  };

  return (
    <div className="space-y-3 border-t py-4 first:border-t-0">
      <div>
        <p className="text-sm font-medium">{submission.title}</p>
        <p className="text-xs text-muted-foreground">
          {team?.name ?? "Unknown team"} &middot; Submitted{" "}
          {new Date(submission.submitted_at).toLocaleString()}
        </p>
      </div>

      {submission.description && <p className="text-sm">{submission.description}</p>}
      <div className="flex gap-4 text-sm">
        {submission.repo_url && (
          <a href={submission.repo_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
            Repository
          </a>
        )}
        {submission.demo_url && (
          <a href={submission.demo_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
            Demo
          </a>
        )}
      </div>

      <div className="flex items-end gap-3">
        <div className="w-24 space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Score</label>
          <Input type="number" min={0} value={score} onChange={(e) => setScore(e.target.value)} />
        </div>
        <div className="flex-1 space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Feedback</label>
          <Textarea
            rows={1}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Optional feedback"
          />
        </div>
        <Button onClick={handleGrade} disabled={gradeMutation.isPending || !score}>
          {submission.score != null ? "Update grade" : "Grade"}
        </Button>
      </div>
    </div>
  );
}
