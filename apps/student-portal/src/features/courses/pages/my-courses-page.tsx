import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EnrollmentListItem } from "@/features/dashboard/components/enrollment-list-item";
import { useMyEnrollments } from "@/features/courses/api/courses-hooks";

export function MyCoursesPage() {
  const { data: enrollments, isLoading } = useMyEnrollments();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">My Courses</h1>
        <p className="text-sm text-muted-foreground">All courses you are currently enrolled in.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Enrollments</CardTitle>
          <CardDescription>Click a course to view chapters, lessons, and progress.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
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
