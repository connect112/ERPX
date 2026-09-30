import { ChevronDown, ChevronRight } from "lucide-react";
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
import { useCancelLeave, useEmployeeLeaveApplications, useLeaveBalances } from "@/features/leave/api/leave-hooks";
import { ApplyLeaveDialog } from "@/features/leave/components/apply-leave-dialog";
import { LeaveStatusBadge } from "@/features/leave/components/leave-status-badge";

export function EmployeeLeavePanel({ employeeId }: { employeeId: string }) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [applyOpen, setApplyOpen] = useState(false);

  const [exceptionOpen, setExceptionOpen] = useState(false);
  const { data: balances, isLoading: balancesLoading } = useLeaveBalances(employeeId, year);
  const { data: applications, isLoading: applicationsLoading } = useEmployeeLeaveApplications(employeeId, {
    limit: 50,
  });
  const cancelLeave = useCancelLeave();

  const years = Array.from({ length: 5 }).map((_, i) => now.getFullYear() - i);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Leave balances</CardTitle>
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
        </CardHeader>
        <CardContent>
          {balancesLoading && <Skeleton className="h-16 w-full" />}
          {!balancesLoading && (balances?.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No leave balances for {year}.
            </p>
          )}
          {!balancesLoading && (balances?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Leave type</TableHead>
                  <TableHead>Quota</TableHead>
                  <TableHead>Used</TableHead>
                  <TableHead>Pending</TableHead>
                  <TableHead>Balance</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {balances?.map((balance) => (
                  <TableRow key={balance.leave_type_id}>
                    <TableCell className="font-medium">{balance.leave_type_name}</TableCell>
                    <TableCell className="text-muted-foreground">{balance.annual_quota}</TableCell>
                    <TableCell className="text-muted-foreground">{balance.days_used}</TableCell>
                    <TableCell className="text-muted-foreground">{balance.days_pending}</TableCell>
                    <TableCell className="font-medium">{balance.balance}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Applications</CardTitle>
        </CardHeader>
        <CardContent>
          {applicationsLoading && <Skeleton className="h-32 w-full" />}
          {!applicationsLoading && (applications?.items.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No leave applications yet.
            </p>
          )}
          {!applicationsLoading && (applications?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Dates</TableHead>
                  <TableHead>Days</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {applications?.items.map((application) => (
                  <TableRow key={application.id}>
                    <TableCell className="text-muted-foreground">
                      {new Date(application.start_date).toLocaleDateString()} –{" "}
                      {new Date(application.end_date).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{application.number_of_days}</TableCell>
                    <TableCell className="max-w-xs truncate text-muted-foreground">
                      {application.reason}
                    </TableCell>
                    <TableCell>
                      <LeaveStatusBadge status={application.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      {application.status === "pending" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => cancelLeave.mutate(application.id)}
                          disabled={cancelLeave.isPending}
                        >
                          Cancel
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="rounded-md border">
        <button
          type="button"
          onClick={() => setExceptionOpen((open) => !open)}
          className="flex w-full items-center gap-2 px-4 py-3 text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          {exceptionOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          Exception — apply for leave on their behalf
        </button>
        {exceptionOpen && (
          <div className="space-y-3 border-t px-4 py-4">
            <p className="text-sm text-muted-foreground">
              Employees should normally apply for their own leave from their portal. Only use this
              if they can't — no portal access, or they called in and asked you to record it.
            </p>
            <Button size="sm" variant="outline" onClick={() => setApplyOpen(true)}>
              Apply for leave
            </Button>
          </div>
        )}
      </div>

      <ApplyLeaveDialog open={applyOpen} onOpenChange={setApplyOpen} defaultEmployeeId={employeeId} />
    </div>
  );
}
