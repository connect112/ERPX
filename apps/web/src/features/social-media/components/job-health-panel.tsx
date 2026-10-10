import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useJobHealth } from "@/features/social-media/api/social-media-hooks";
import { formatInZone } from "@/features/social-media/lib/format";

const STATE_LABEL = { ok: "Running", late: "Not running when it should", failed: "Failed on its last run", never: "Not run yet", idle: "Waiting for an Instagram connection" } as const;
const STATE_VARIANT = { ok: "success", late: "warning", failed: "destructive", never: "secondary", idle: "outline" } as const;

function every(minutes: number): string {
  if (minutes >= 1440) return "every day";
  if (minutes >= 60) return `every ${minutes / 60} hour(s)`;
  return minutes === 1 ? "every minute" : `every ${minutes} minutes`;
}

/** Whether the machinery behind the page (publishing, reading comments, insights, reports) is actually running. */
export function JobHealthPanel() {
  const health = useJobHealth();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Background jobs</CardTitle>
        <CardDescription>{health.data?.note ?? "Whether the scheduled work behind this page is running."}</CardDescription>
      </CardHeader>
      <CardContent>
        {health.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : health.isError || !health.data ? (
          <p className="text-sm text-destructive">Couldn&apos;t load the job status.</p>
        ) : (
          <ul className="space-y-2">
            {health.data.jobs.map((j) => (
              <li key={j.key} className="flex flex-wrap items-start justify-between gap-2 rounded-md border p-3 text-sm">
                <div className="min-w-0">
                  <p className="font-medium">{j.label}</p>
                  <p className="text-xs text-muted-foreground">
                    Runs {every(j.runs_every_minutes)}
                    {j.last_finished_at ? ` · last finished ${formatInZone(j.last_finished_at, "Asia/Kolkata")}` : ""}
                  </p>
                  {j.last_error && <p className="text-xs text-destructive">{j.last_error}</p>}
                </div>
                <Badge variant={STATE_VARIANT[j.state]}>{STATE_LABEL[j.state]}</Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
