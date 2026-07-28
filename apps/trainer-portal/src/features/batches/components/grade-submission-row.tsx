import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useGradeSubmission } from "@/features/batches/api/batches-hooks";
import type { SubmissionPublic } from "@/features/batches/api/batches-api";

interface GradeSubmissionRowProps {
  courseId: string;
  assignmentId: string;
  submission: SubmissionPublic;
  maxScore: number;
}

export function GradeSubmissionRow({
  courseId,
  assignmentId,
  submission,
  maxScore,
}: GradeSubmissionRowProps) {
  const [score, setScore] = useState(submission.score?.toString() ?? "");
  const [feedback, setFeedback] = useState(submission.feedback ?? "");
  const gradeMutation = useGradeSubmission(courseId, assignmentId);

  const handleGrade = () => {
    const parsedScore = Number(score);
    if (Number.isNaN(parsedScore) || parsedScore < 0 || parsedScore > maxScore) return;
    gradeMutation.mutate({ submissionId: submission.id, score: parsedScore, feedback });
  };

  return (
    <div className="space-y-3 border-t py-4 first:border-t-0">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">{submission.student_name}</p>
          <p className="text-xs text-muted-foreground">
            Submitted {new Date(submission.submitted_at).toLocaleString()}
          </p>
        </div>
        <Badge variant="outline" className="capitalize">
          {submission.status}
        </Badge>
      </div>

      {submission.content_text && (
        <p className="rounded-md bg-muted/50 p-3 text-sm">{submission.content_text}</p>
      )}
      {submission.content_url && (
        <a
          href={submission.content_url}
          target="_blank"
          rel="noreferrer"
          className="text-sm text-primary hover:underline"
        >
          View submission attachment
        </a>
      )}

      <div className="flex items-end gap-3">
        <div className="w-24 space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Score / {maxScore}</label>
          <Input
            type="number"
            min={0}
            max={maxScore}
            value={score}
            onChange={(e) => setScore(e.target.value)}
          />
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
          {submission.status === "graded" ? "Update grade" : "Grade"}
        </Button>
      </div>
    </div>
  );
}
