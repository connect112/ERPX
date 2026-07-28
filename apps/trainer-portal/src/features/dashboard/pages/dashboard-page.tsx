import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyBatches } from "@/features/batches/api/batches-hooks";
import { useMyTrainerProfile } from "@/features/dashboard/api/trainer-hooks";

export function DashboardPage() {
  const { data: trainer, isLoading: trainerLoading } = useMyTrainerProfile();
  const { data: batches, isLoading: batchesLoading } = useMyBatches();

  const ongoingCount = batches?.filter((b) => b.status === "ongoing").length ?? 0;
  const upcomingCount = batches?.filter((b) => b.status === "upcoming").length ?? 0;

  return (
    <div className="space-y-6 p-6">
      <div>
        {trainerLoading ? (
          <Skeleton className="h-8 w-64" />
        ) : (
          <h1 className="text-2xl font-semibold">Welcome back, {trainer?.employee_name}</h1>
        )}
        <p className="text-sm text-muted-foreground">Here's an overview of your teaching load.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Ongoing batches</CardDescription>
            <CardTitle className="text-lg">{batchesLoading ? "…" : ongoingCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Upcoming batches</CardDescription>
            <CardTitle className="text-lg">{batchesLoading ? "…" : upcomingCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Specializations</CardDescription>
            <CardTitle className="text-lg">{trainer?.specializations ?? "—"}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">My Batches</CardTitle>
          <CardDescription>Batches you are currently assigned to teach.</CardDescription>
        </CardHeader>
        <CardContent>
          {batchesLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : batches && batches.length > 0 ? (
            <ul className="divide-y">
              {batches.map((batch) => (
                <li key={batch.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">{batch.name}</p>
                    <p className="text-xs text-muted-foreground">{batch.course_title}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="capitalize">
                      {batch.status}
                    </Badge>
                    <Link
                      to={`/batches/${batch.id}`}
                      className="text-sm font-medium text-primary hover:underline"
                    >
                      View
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              You have not been assigned to any batches yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
