import { format, parseISO } from "date-fns";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyAnnouncements } from "@/features/announcements/api/announcements-hooks";

export function AnnouncementsPage() {
  const { data, isLoading } = useMyAnnouncements();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Announcements</h1>
        <p className="text-sm text-muted-foreground">
          Org-wide updates and anything posted for a course you teach. Read-only — posting is an admin
          action.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : data && data.length > 0 ? (
        <div className="space-y-4">
          {data.map((a) => (
            <Card key={a.id}>
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <CardTitle className="text-base">{a.title}</CardTitle>
                <div className="flex items-center gap-2">
                  {a.course_id === null && <Badge variant="secondary">Org-wide</Badge>}
                  <span className="text-xs text-muted-foreground">
                    {format(parseISO(a.published_at), "PPp")}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap text-sm">{a.body}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">No announcements yet.</p>
      )}
    </div>
  );
}
