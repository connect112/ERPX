import { format, parseISO } from "date-fns";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useMyLiveClasses, useMyTimetable } from "@/features/schedule/api/schedule-hooks";
import type { DayOfWeek } from "@/features/schedule/api/schedule-api";

const DAY_ORDER: DayOfWeek[] = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

function dayLabel(day: DayOfWeek): string {
  return day.charAt(0).toUpperCase() + day.slice(1);
}

function timeLabel(time: string): string {
  // Backend sends "HH:MM:SS" — render as a plain 24h "HH:MM".
  return time.slice(0, 5);
}

const statusVariant: Record<string, "default" | "success" | "secondary" | "outline"> = {
  scheduled: "default",
  live: "success",
  completed: "secondary",
  cancelled: "outline",
};

export function MySchedulePage() {
  const { data: timetable, isLoading: timetableLoading } = useMyTimetable();
  const { data: liveClasses, isLoading: liveClassesLoading } = useMyLiveClasses();

  const sortedTimetable = [...(timetable ?? [])].sort((a, b) => {
    const dayDiff = DAY_ORDER.indexOf(a.day_of_week) - DAY_ORDER.indexOf(b.day_of_week);
    return dayDiff !== 0 ? dayDiff : a.start_time.localeCompare(b.start_time);
  });

  const upcomingLiveClasses = [...(liveClasses ?? [])].sort(
    (a, b) => new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime()
  );

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">My Schedule</h1>
        <p className="text-sm text-muted-foreground">
          Your batch's weekly timetable and live class sessions. Read-only — reach out to your
          trainer or admin for schedule changes.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Weekly Timetable</CardTitle>
          <CardDescription>Recurring sessions for your enrolled batch.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {timetableLoading ? (
            <div className="space-y-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : sortedTimetable.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Day</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>Subject</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedTimetable.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="font-medium">{dayLabel(entry.day_of_week)}</TableCell>
                    <TableCell>
                      {timeLabel(entry.start_time)} – {timeLabel(entry.end_time)}
                    </TableCell>
                    <TableCell>{entry.subject ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No timetable entries yet — you may not be assigned to a batch.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Live Classes</CardTitle>
          <CardDescription>One-off sessions — join links appear here when scheduled.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {liveClassesLoading ? (
            <div className="space-y-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : upcomingLiveClasses.length > 0 ? (
            <ul className="divide-y">
              {upcomingLiveClasses.map((liveClass) => (
                <li key={liveClass.id} className="flex items-center justify-between gap-4 p-4">
                  <div>
                    <p className="font-medium">{liveClass.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {format(parseISO(liveClass.scheduled_at), "PPp")} · {liveClass.duration_minutes} min
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={statusVariant[liveClass.status] ?? "default"}>
                      {liveClass.status}
                    </Badge>
                    {liveClass.status === "completed" && liveClass.recording_url ? (
                      <Button asChild size="sm" variant="outline">
                        <a href={liveClass.recording_url} target="_blank" rel="noreferrer">
                          Recording
                        </a>
                      </Button>
                    ) : (liveClass.status === "scheduled" || liveClass.status === "live") &&
                      liveClass.meeting_link ? (
                      <Button asChild size="sm">
                        <a href={liveClass.meeting_link} target="_blank" rel="noreferrer">
                          Join
                        </a>
                      </Button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No live classes scheduled yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
