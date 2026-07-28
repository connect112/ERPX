import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCoursesList } from "@/features/courses/api/courses-hooks";
import { useStudentCourseResult } from "@/features/examinations/results/api/results-hooks";
import { useEnrollmentsForStudent } from "@/features/lms/enrollment/api/enrollment-hooks";

export function StudentResultsPanel({ studentId }: { studentId: string }) {
  const { data: enrollments } = useEnrollmentsForStudent(studentId);
  const { data: courses } = useCoursesList({ limit: 200 });
  const [courseId, setCourseId] = useState("");

  const { data: result, isLoading, isError } = useStudentCourseResult(studentId, courseId);

  const courseTitle = (id: string) => courses?.items.find((c) => c.id === id)?.title ?? id;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Examination Results</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Select value={courseId || undefined} onValueChange={setCourseId}>
          <SelectTrigger className="sm:w-64">
            <SelectValue placeholder="Select a course" />
          </SelectTrigger>
          <SelectContent>
            {enrollments?.map((e) => (
              <SelectItem key={e.course_id} value={e.course_id}>
                {courseTitle(e.course_id)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {!courseId && (
          <p className="text-sm text-muted-foreground">
            Select a course to view exam, practical, and viva results.
          </p>
        )}

        {courseId && isLoading && <Skeleton className="h-32 w-full" />}

        {courseId && isError && (
          <p className="text-sm text-muted-foreground">No results available for this course yet.</p>
        )}

        {courseId && result && (
          <div className="space-y-3">
            <div className="flex items-center gap-3 rounded-md border p-3">
              <div>
                <p className="text-sm text-muted-foreground">Overall</p>
                <p className="text-lg font-semibold">
                  {result.overall_score} / {result.overall_total} ({result.overall_percentage.toFixed(1)}%)
                </p>
              </div>
              <Badge
                variant={
                  result.overall_status === "pass"
                    ? "success"
                    : result.overall_status === "fail"
                      ? "destructive"
                      : "secondary"
                }
                className="ml-auto"
              >
                {result.overall_status}
              </Badge>
            </div>

            <div className="space-y-2">
              {result.components.map((component) => (
                <div
                  key={`${component.component_type}-${component.component_id}`}
                  className="flex items-center justify-between rounded border px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium">{component.title}</p>
                    <p className="text-xs capitalize text-muted-foreground">{component.component_type}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      {component.score ?? "—"} / {component.total_marks}
                    </span>
                    {component.passed === null ? (
                      <Badge variant="secondary">Pending</Badge>
                    ) : (
                      <Badge variant={component.passed ? "success" : "destructive"}>
                        {component.passed ? "Passed" : "Failed"}
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
