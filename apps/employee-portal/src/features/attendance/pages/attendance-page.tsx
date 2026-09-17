import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCheckIn, useCheckOut, useMyAttendance } from "@/features/attendance/api/attendance-hooks";

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function AttendancePage() {
  const { data, isLoading } = useMyAttendance();
  const checkInMutation = useCheckIn();
  const checkOutMutation = useCheckOut();

  const todayRecord = data?.items.find((r) => r.attendance_date === todayISO());
  const canCheckIn = !todayRecord || !todayRecord.check_in_time;
  const canCheckOut = todayRecord?.check_in_time && !todayRecord.check_out_time;

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Attendance</h1>
        <p className="text-sm text-muted-foreground">Check in and out, and review your recent history.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Today</CardTitle>
          <CardDescription>
            {todayRecord?.check_in_time
              ? `Checked in at ${new Date(todayRecord.check_in_time).toLocaleTimeString()}`
              : "You haven't checked in yet today."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-3">
          <Button
            onClick={() => checkInMutation.mutate()}
            disabled={!canCheckIn || checkInMutation.isPending}
          >
            Check in
          </Button>
          <Button
            variant="outline"
            onClick={() => checkOutMutation.mutate()}
            disabled={!canCheckOut || checkOutMutation.isPending}
          >
            Check out
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent history</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : data && data.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Check-in</TableHead>
                  <TableHead>Check-out</TableHead>
                  <TableHead>Hours</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((record) => (
                  <TableRow key={record.id}>
                    <TableCell>{record.attendance_date}</TableCell>
                    <TableCell>
                      {record.check_in_time
                        ? new Date(record.check_in_time).toLocaleTimeString()
                        : "—"}
                    </TableCell>
                    <TableCell>
                      {record.check_out_time
                        ? new Date(record.check_out_time).toLocaleTimeString()
                        : "—"}
                    </TableCell>
                    <TableCell>{record.work_hours ?? "—"}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">
                        {record.status.replace("_", " ")}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">No attendance records yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
