import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EnrollmentListItem } from "@/features/dashboard/components/enrollment-list-item";
import { useMyStudentProfile } from "@/features/dashboard/api/student-hooks";
import { useMyEnrollments } from "@/features/courses/api/courses-hooks";

export function DashboardPage() {
  const { data: student, isLoading: studentLoading } = useMyStudentProfile();
  const { data: enrollments, isLoading: enrollmentsLoading } = useMyEnrollments();

  const activeCount = enrollments?.filter((e) => e.status === "active").length ?? 0;
  const completedCount = enrollments?.filter((e) => e.status === "completed").length ?? 0;

  return (
    <div className="space-y-6 p-6">
      <div>
        {studentLoading ? (
          <Skeleton className="h-8 w-64" />
        ) : (
          <h1 className="text-2xl font-semibold">Welcome back, {student?.full_name}</h1>
        )}
        <p className="text-sm text-muted-foreground">
          Here's an overview of your enrollment and progress.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Student code</CardDescription>
            <CardTitle className="text-lg">{studentLoading ? "…" : student?.student_code}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Active courses</CardDescription>
            <CardTitle className="text-lg">{enrollmentsLoading ? "…" : activeCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Completed courses</CardDescription>
            <CardTitle className="text-lg">{enrollmentsLoading ? "…" : completedCount}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">My Enrollments</CardTitle>
          <CardDescription>Your currently enrolled and past courses.</CardDescription>
        </CardHeader>
        <CardContent>
          {enrollmentsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : enrollments && enrollments.length > 0 ? (
            <ul className="divide-y">
              {enrollments.map((enrollment) => (
                <EnrollmentListItem key={enrollment.id} enrollment={enrollment} />
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              You are not enrolled in any courses yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
