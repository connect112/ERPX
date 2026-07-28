import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAttendanceSummary, useEmployeeAttendance } from "@/features/attendance/api/attendance-hooks";
import { AttendanceStatusBadge } from "@/features/attendance/components/attendance-status-badge";
import { MarkAttendanceDialog } from "@/features/attendance/components/mark-attendance-dialog";

const monthNames = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function EmployeeAttendancePanel({ employeeId }: { employeeId: string }) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [markOpen, setMarkOpen] = useState(false);

  const { data: summary, isLoading: summaryLoading } = useAttendanceSummary(employeeId, year, month);
  const { data: records, isLoading: recordsLoading } = useEmployeeAttendance(employeeId, { limit: 50 });

  const years = Array.from({ length: 5 }).map((_, i) => now.getFullYear() - i);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Monthly summary</CardTitle>
          <div className="flex items-center gap-2">
            <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {monthNames.map((name, i) => (
                  <SelectItem key={name} value={String(i + 1)}>
                    {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {years.map((y) => (
                  <SelectItem key={y} value={String(y)}>
                    {y}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button size="sm" onClick={() => setMarkOpen(true)}>
              Mark attendance
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {summaryLoading && <Skeleton className="h-16 w-full" />}
          {summary && (
            <div className="grid grid-cols-3 gap-4 sm:grid-cols-6">
              <div>
                <p className="text-xs text-muted-foreground">Present</p>
                <p className="text-lg font-semibold">{summary.present_days}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Absent</p>
                <p className="text-lg font-semibold">{summary.absent_days}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Half day</p>
                <p className="text-lg font-semibold">{summary.half_days}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">On leave</p>
                <p className="text-lg font-semibold">{summary.leave_days}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Holidays</p>
                <p className="text-lg font-semibold">{summary.holiday_days}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Work hours</p>
                <p className="text-lg font-semibold">{summary.total_work_hours.toFixed(1)}</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Attendance records</CardTitle>
        </CardHeader>
        <CardContent>
          {recordsLoading && <Skeleton className="h-32 w-full" />}
          {!recordsLoading && (records?.items.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No attendance records yet.</p>
          )}
          {!recordsLoading && (records?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Check-in</TableHead>
                  <TableHead>Check-out</TableHead>
                  <TableHead>Work hours</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {records?.items.map((record) => (
                  <TableRow key={record.id}>
                    <TableCell className="text-muted-foreground">
                      {new Date(record.attendance_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {record.check_in_time ? new Date(record.check_in_time).toLocaleTimeString() : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {record.check_out_time ? new Date(record.check_out_time).toLocaleTimeString() : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {record.work_hours != null ? record.work_hours.toFixed(2) : "—"}
                    </TableCell>
                    <TableCell>
                      <AttendanceStatusBadge status={record.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <MarkAttendanceDialog open={markOpen} onOpenChange={setMarkOpen} defaultEmployeeId={employeeId} />
    </div>
  );
}
