import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyBatches } from "@/features/batches/api/batches-hooks";

export function MyBatchesPage() {
  const { data: batches, isLoading } = useMyBatches();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">My Batches</h1>
        <p className="text-sm text-muted-foreground">Batches you are assigned to teach.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Assigned Batches</CardTitle>
          <CardDescription>Click a batch to view its assignments and grade submissions.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
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
                    <p className="text-xs text-muted-foreground">
                      {batch.course_title} &middot; {batch.code}
                    </p>
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
