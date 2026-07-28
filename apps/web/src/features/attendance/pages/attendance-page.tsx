import { LogIn, LogOut, Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAttendanceList } from "@/features/attendance/api/attendance-hooks";
import { AttendanceStatusBadge } from "@/features/attendance/components/attendance-status-badge";
import { CheckInOutDialog } from "@/features/attendance/components/check-in-out-dialog";
import { MarkAttendanceDialog } from "@/features/attendance/components/mark-attendance-dialog";
import type { AttendanceRecordPublic } from "@/features/attendance/api/attendance-api";
import { RegularizeAttendanceDialog } from "@/features/attendance/components/regularize-attendance-dialog";
import {
  type AttendanceStatus,
  attendanceStatusLabels,
  attendanceStatusValues,
} from "@/features/attendance/schemas/attendance-schemas";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";

const PAGE_SIZE = 20;

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export function AttendancePage() {
  const [date, setDate] = useState(todayIso());
  const [status, setStatus] = useState<AttendanceStatus | "all">("all");
  const [skip, setSkip] = useState(0);
  const [markOpen, setMarkOpen] = useState(false);
  const [checkDialog, setCheckDialog] = useState<"check-in" | "check-out" | null>(null);
  const [regularizeTarget, setRegularizeTarget] = useState<AttendanceRecordPublic | null>(null);

  const { data, isLoading, isError } = useAttendanceList({
    attendance_date: date || undefined,
    status: status === "all" ? undefined : status,
    skip,
    limit: PAGE_SIZE,
  });
  const { data: employees } = useEmployeesList({ limit: 200 });
  const employeeName = (id: string) =>
    employees?.items.find((e) => e.id === id)?.full_name ?? id;

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Attendance</h1>
          <p className="mt-1 text-muted-foreground">
            Track daily check-ins, check-outs, and attendance status.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setCheckDialog("check-in")}>
            <LogIn className="h-4 w-4" />
            Check in
          </Button>
          <Button variant="outline" onClick={() => setCheckDialog("check-out")}>
            <LogOut className="h-4 w-4" />
            Check out
          </Button>
          <Button onClick={() => setMarkOpen(true)}>
            <Plus className="h-4 w-4" />
            Mark attendance
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <Input
              type="date"
              className="sm:w-48"
              value={date}
              onChange={(e) => {
                setDate(e.target.value);
                setSkip(0);
              }}
            />
            <Select
              value={status}
              onValueChange={(value) => {
                setStatus(value as AttendanceStatus | "all");
                setSkip(0);
              }}
            >
              <SelectTrigger className="sm:w-48">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {attendanceStatusValues.map((s) => (
                  <SelectItem key={s} value={s}>
                    {attendanceStatusLabels[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load attendance records. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No attendance records found for this filter.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Check-in</TableHead>
                  <TableHead>Check-out</TableHead>
                  <TableHead>Work hours</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((record) => (
                  <TableRow key={record.id}>
                    <TableCell className="font-medium">{employeeName(record.employee_id)}</TableCell>
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
                      <div className="flex items-center gap-2">
                        <AttendanceStatusBadge status={record.status} />
                        {record.is_regularized && (
                          <span className="text-xs text-muted-foreground">(regularized)</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => setRegularizeTarget(record)}>
                        Regularize
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} records)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip + PAGE_SIZE >= total}
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <MarkAttendanceDialog open={markOpen} onOpenChange={setMarkOpen} />
      <CheckInOutDialog
        open={!!checkDialog}
        onOpenChange={(open) => !open && setCheckDialog(null)}
        mode={checkDialog ?? "check-in"}
      />
      <RegularizeAttendanceDialog
        open={!!regularizeTarget}
        onOpenChange={(open) => !open && setRegularizeTarget(null)}
        record={regularizeTarget}
      />
    </div>
  );
}
