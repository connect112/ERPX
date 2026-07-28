import { useParams } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { GradeSubmissionRow } from "@/features/batches/components/grade-submission-row";
import {
  useMyBatches,
  useMyCourseAssignments,
  useMySubmissions,
} from "@/features/batches/api/batches-hooks";

export function AssignmentGradingPage() {
  const { batchId, assignmentId } = useParams<{ batchId: string; assignmentId: string }>();
  const { data: batches } = useMyBatches();
  const batch = batches?.find((b) => b.id === batchId);

  const { data: assignments } = useMyCourseAssignments(batch?.course_id);
  const assignment = assignments?.find((a) => a.id === assignmentId);

  const { data: submissions, isLoading } = useMySubmissions(batch?.course_id, assignmentId);

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">{assignment?.title ?? "Assignment"}</h1>
        <p className="text-sm text-muted-foreground">
          {batch?.name} &middot; {batch?.course_title}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Submissions</CardTitle>
          <CardDescription>Review and grade each student's submission.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : submissions && submissions.length > 0 && assignment ? (
            <div>
              {submissions.map((submission) => (
                <GradeSubmissionRow
                  key={submission.id}
                  courseId={batch!.course_id}
                  assignmentId={assignmentId as string}
                  submission={submission}
                  maxScore={assignment.max_score}
                />
              ))}
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No students have submitted this assignment yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
