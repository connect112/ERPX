import { ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PORTAL_URLS } from "@/features/auth/lib/portal-resolution";
import { useMyInternships } from "@/features/internships/api/internships-api";
import { accessText } from "@/features/internships/lib/access-text";

/**
 * Internships the admin has given this trainer. The full screens (students, exams, assignments, projects, awards,
 * certificates) live on the admin site, which accepts the same login; the admin site shows only these internships.
 */
export function MyInternshipsPage() {
  const { data, isLoading, isError } = useMyInternships();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">My Internships</h1>
        <p className="text-sm text-muted-foreground">
          Internships you have been given access to. You can add, edit, view, mark and validate, but not delete.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Assigned Internships</CardTitle>
          <CardDescription>Open one to work on its students, exams, assignments, projects and certificates.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : isError ? (
            <p className="py-6 text-center text-sm text-destructive">Could not load your internships.</p>
          ) : data && data.length > 0 ? (
            <ul className="divide-y">
              {data.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div>
                    <p className="text-sm font-medium">{i.title}</p>
                    <p className="text-xs text-muted-foreground">{accessText(i.access_until)}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className="capitalize">
                      {i.status}
                    </Badge>
                    <a
                      href={`${PORTAL_URLS.admin}/our-internships/${i.id}`}
                      className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                    >
                      Open
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              You have no internships right now. When an administrator gives you access for a period, it appears here and
              disappears when the period ends.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
