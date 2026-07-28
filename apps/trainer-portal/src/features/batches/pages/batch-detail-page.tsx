import { Link, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyBatches, useMyCourseAssignments } from "@/features/batches/api/batches-hooks";

export function BatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const { data: batches, isLoading: batchesLoading } = useMyBatches();
  const batch = batches?.find((b) => b.id === batchId);

  const { data: assignments, isLoading: assignmentsLoading } = useMyCourseAssignments(
    batch?.course_id
  );

  return (
    <div className="space-y-6 p-6">
      <div>
        {batchesLoading ? (
          <Skeleton className="h-8 w-64" />
        ) : (
          <h1 className="text-2xl font-semibold">{batch?.name}</h1>
        )}
        {batch && (
          <p className="text-sm text-muted-foreground">
            {batch.course_title} &middot; {batch.code}
          </p>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Assignments</CardTitle>
          <CardDescription>Select an assignment to view and grade student submissions.</CardDescription>
        </CardHeader>
        <CardContent>
          {assignmentsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : assignments && assignments.length > 0 ? (
            <ul className="divide-y">
              {assignments.map((assignment) => (
                <li key={assignment.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">{assignment.title}</p>
                    <p className="text-xs text-muted-foreground">Max score: {assignment.max_score}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {assignment.due_date && (
                      <Badge variant="outline">
                        Due {new Date(assignment.due_date).toLocaleDateString()}
                      </Badge>
                    )}
                    <Link
                      to={`/batches/${batchId}/assignments/${assignment.id}`}
                      className="text-sm font-medium text-primary hover:underline"
                    >
                      Grade
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No assignments have been created for this course yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
