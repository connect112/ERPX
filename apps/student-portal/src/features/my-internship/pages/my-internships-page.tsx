import { Link, Navigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyInternshipList } from "@/features/my-internship/api/my-internship-api";

/** Every internship the student has been given access to. With just one, it opens straight away. */
export function MyInternshipsPage() {
  const { data, isLoading, isError } = useMyInternshipList();

  if (isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  if (isError) return <p className="p-6 text-sm text-destructive">Could not load your internships.</p>;
  if (data?.length === 1) return <Navigate to={`/my-internship/${data[0].id}`} replace />;

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">My Internship</h1>
        <p className="text-sm text-muted-foreground">Your exams, assignments and projects.</p>
      </div>
      {!data || data.length === 0 ? (
        <p className="rounded-md border bg-card p-8 text-center text-sm text-muted-foreground">
          You are not enrolled on an internship yet. It appears here once your access has been set up.
        </p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((i) => (
            <Link key={i.id} to={`/my-internship/${i.id}`}>
              <Card className="h-full transition-colors hover:bg-muted/40">
                <CardHeader>
                  <CardTitle className="text-base">{i.title}</CardTitle>
                  {i.description && <CardDescription className="line-clamp-2">{i.description}</CardDescription>}
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2">
                  <Badge variant={i.open_assignments ? "warning" : "secondary"}>
                    {i.open_assignments} open assignment{i.open_assignments === 1 ? "" : "s"}
                  </Badge>
                  <Badge variant={i.open_exams ? "info" : "secondary"}>
                    {i.open_exams} exam{i.open_exams === 1 ? "" : "s"} to take
                  </Badge>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
