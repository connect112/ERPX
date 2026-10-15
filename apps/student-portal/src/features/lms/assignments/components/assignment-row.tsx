import { format, parseISO } from "date-fns";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  useMySubmission,
  useSubmitAssignment,
} from "@/features/lms/assignments/api/assignments-hooks";
import type { AssignmentPublic, SubmissionStatus } from "@/features/lms/assignments/api/assignments-api";

const statusVariant: Record<SubmissionStatus, "default" | "success" | "warning"> = {
  submitted: "default",
  graded: "success",
  late: "warning",
};

const statusLabel: Record<SubmissionStatus, string> = {
  submitted: "Submitted",
  graded: "Graded",
  late: "Submitted late",
};

export function AssignmentRow({ courseId, assignment }: { courseId: string; assignment: AssignmentPublic }) {
  const { data: submission, isLoading } = useMySubmission(courseId, assignment.id);
  const submitMutation = useSubmitAssignment(courseId, assignment.id);
  const [contentText, setContentText] = useState("");
  const [contentUrl, setContentUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  const isPastDue = assignment.due_date ? new Date(assignment.due_date) < new Date() : false;

  const handleSubmit = async () => {
    setError(null);
    if (!contentText.trim() && !contentUrl.trim()) {
      setError("Add a response or a link before submitting.");
      return;
    }
    try {
      await submitMutation.mutateAsync({
        content_text: contentText.trim() || undefined,
        content_url: contentUrl.trim() || undefined,
      });
    } catch {
      setError("Couldn't submit — please try again.");
    }
  };

  return (
    <div className="border-b p-4 last:border-0">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium">{assignment.title}</p>
          {assignment.description && (
            <p className="mt-1 text-sm text-muted-foreground">{assignment.description}</p>
          )}
          <p className="mt-1 text-xs text-muted-foreground">
            {assignment.due_date
              ? `Due ${format(parseISO(assignment.due_date), "PP")}`
              : "No due date"}{" "}
            · Max score {assignment.max_score}
          </p>
        </div>
        {submission && <Badge variant={statusVariant[submission.status]}>{statusLabel[submission.status]}</Badge>}
      </div>

      {isLoading ? (
        <Skeleton className="mt-3 h-16 w-full" />
      ) : submission ? (
        <div className="mt-3 space-y-2 rounded-md bg-muted/50 p-3 text-sm">
          {submission.content_text && <p className="whitespace-pre-wrap">{submission.content_text}</p>}
          {submission.content_url && (
            <a
              href={submission.content_url}
              target="_blank"
              rel="noreferrer"
              className="block text-primary hover:underline"
            >
              {submission.content_url}
            </a>
          )}
          <p className="text-xs text-muted-foreground">
            Submitted {format(parseISO(submission.submitted_at), "PPp")}
          </p>
          {submission.status === "graded" && (
            <div className="border-t pt-2">
              <p className="font-medium">
                Score: {submission.score} / {assignment.max_score}
              </p>
              {submission.feedback && (
                <p className="mt-1 text-muted-foreground">{submission.feedback}</p>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          {isPastDue && (
            <p className="text-xs text-amber-800 dark:text-amber-400">
              This assignment is past its due date — a submission now will be marked late.
            </p>
          )}
          <Textarea
            placeholder="Write your response…"
            value={contentText}
            onChange={(e) => setContentText(e.target.value)}
            rows={4}
          />
          <Input
            placeholder="Optional link to your work (e.g. a doc or repo URL)"
            value={contentUrl}
            onChange={(e) => setContentUrl(e.target.value)}
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button size="sm" disabled={submitMutation.isPending} onClick={handleSubmit}>
            {submitMutation.isPending ? "Submitting…" : "Submit assignment"}
          </Button>
        </div>
      )}
    </div>
  );
}
