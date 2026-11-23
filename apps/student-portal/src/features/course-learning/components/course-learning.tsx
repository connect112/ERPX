import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { type MyEvaluation, useCourseLearning } from "@/features/course-learning/api/course-learning-api";

function Grades({ title, rows, empty }: { title: string; rows: MyEvaluation[]; empty: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">{empty}</p>
        ) : (
          <ul className="divide-y">
            {rows.map((r) => (
              <li key={r.id} className="space-y-1 py-2 text-sm" data-testid={`grade-${r.title}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{r.title}</span>
                  <span className="text-muted-foreground">{new Date(r.exam_date).toLocaleDateString("en-GB")}</span>
                </div>
                {r.detail && <p className="whitespace-pre-wrap text-xs text-muted-foreground">{r.detail}</p>}
                {r.score != null ? (
                  <p>
                    {r.score} / {r.total_marks}{" "}
                    <Badge variant={r.passed ? "success" : "destructive"}>{r.passed ? "Pass" : "Not passed"}</Badge>
                    {r.remarks && <span className="ml-2 text-muted-foreground">“{r.remarks}”</span>}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">No result recorded yet.</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * The student's own learning in a course, beyond the lessons: the internships that gave them this course (their activities stay under My
 * Internship, so nothing is listed twice), assessments they can take, their practical and viva grades, and the course discussions. It is
 * their own data only; if their access was withdrawn the whole section is simply absent.
 */
export function CourseLearning({ courseId }: { courseId: string }) {
  const { data, isLoading, isError } = useCourseLearning(courseId);
  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (isError || !data) return null;

  return (
    <div className="space-y-6" data-testid="course-learning">
      {data.internships.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Your internship work</CardTitle>
            <CardDescription>Exams, assignments and projects for this course are under My Internship, in one place.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.internships.map((i) => (
              <div key={i.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="font-medium">{i.title}</span>
                <span className="text-muted-foreground">
                  {i.open_assignments} open assignment{i.open_assignments === 1 ? "" : "s"} · {i.open_exams} open exam{i.open_exams === 1 ? "" : "s"}
                </span>
                <Button asChild size="sm" variant="outline">
                  <Link to={`/my-internship/${i.id}`}>Open</Link>
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Assessments and quizzes</CardTitle>
        </CardHeader>
        <CardContent>
          {data.assessments.length === 0 ? (
            <p className="text-sm text-muted-foreground">There are no assessments for you yet.</p>
          ) : (
            <ul className="divide-y">
              {data.assessments.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm" data-testid={`assessment-${a.title}`}>
                  <span>
                    <span className="font-medium">{a.title}</span>
                    <span className="ml-2 text-muted-foreground">
                      {a.total_marks} marks{a.duration_minutes ? ` · ${a.duration_minutes} min` : ""}
                    </span>
                    {a.internship_id && <Badge className="ml-2" variant="info">Internship</Badge>}
                  </span>
                  {a.state === "submitted" ? (
                    <span>
                      {a.score != null ? `${a.score} / ${a.result_total}` : "Submitted"}
                      {a.passed != null && <Badge className="ml-2" variant={a.passed ? "success" : "destructive"}>{a.passed ? "Pass" : "Not passed"}</Badge>}
                    </span>
                  ) : a.has_questions ? (
                    <Button asChild size="sm">
                      <Link to={`/courses/${courseId}/assessments/${a.id}`}>{a.state === "in_progress" ? "Continue" : "Start"}</Link>
                    </Button>
                  ) : (
                    <span className="text-muted-foreground">Your instructor records this result</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Grades title="Practicals" rows={data.practicals} empty="No practicals for you yet." />
        <Grades title="Viva" rows={data.viva} empty="No viva evaluations for you yet." />
      </div>

      <Card>
        <CardContent className="flex items-center justify-between p-4 text-sm">
          <span>Ask a question or follow the course conversation.</span>
          <Button asChild size="sm" variant="outline">
            <Link to={`/courses/${courseId}/discussions`}>Open discussions</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
