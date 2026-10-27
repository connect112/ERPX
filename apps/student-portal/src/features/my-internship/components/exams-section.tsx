import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { type MyExam, useMyExams } from "@/features/my-internship/api/my-internship-api";
import { formatDateTime } from "@/features/my-internship/lib/format";

function action(exam: MyExam): { label: string; enabled: boolean } {
  if (exam.state === "submitted") return { label: "Submitted", enabled: false };
  if (exam.status === "closed") return { label: "Closed", enabled: false };
  return { label: exam.state === "in_progress" ? "Continue exam" : "Start exam", enabled: true };
}

/** The exams the student is on. Each opens the exam page with their personal link. */
export function ExamsSection({ internshipId }: { internshipId: string }) {
  const { data, isLoading, isError } = useMyExams(internshipId);
  if (isLoading) return <Skeleton className="h-32 w-full" />;
  if (isError) return <p className="text-sm text-destructive">Could not load your exams.</p>;
  if (!data || data.length === 0) {
    return <p className="rounded-md border bg-card p-8 text-center text-sm text-muted-foreground">No exams have been assigned to you yet.</p>;
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {data.map((exam) => {
        const a = action(exam);
        return (
          <Card key={exam.id}>
            <CardHeader>
              <div className="flex items-start justify-between gap-2">
                <CardTitle className="text-base">{exam.title}</CardTitle>
                <Badge variant={exam.state === "submitted" ? "success" : exam.state === "in_progress" ? "warning" : "info"}>
                  {exam.state === "submitted" ? "Submitted" : exam.state === "in_progress" ? "In progress" : "Not started"}
                </Badge>
              </div>
              <CardDescription>{exam.duration_minutes} minutes</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {exam.description && <p className="text-sm text-muted-foreground">{exam.description}</p>}
              {exam.state === "submitted" && (
                <p className="text-sm">
                  Submitted {formatDateTime(exam.submitted_at)}
                  {exam.score !== null && exam.total_marks !== null && (
                    <>
                      {" "}
                      · Score <strong>{exam.score}</strong> / {exam.total_marks}
                    </>
                  )}
                </p>
              )}
              {a.enabled ? (
                <Button asChild>
                  <a href={exam.url} target="_blank" rel="noreferrer">
                    {a.label}
                  </a>
                </Button>
              ) : (
                <Button disabled variant="outline">
                  {a.label}
                </Button>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
