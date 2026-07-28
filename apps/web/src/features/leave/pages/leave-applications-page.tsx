import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import { useApproveLeave, useLeaveApplications, useLeaveTypes } from "@/features/leave/api/leave-hooks";
import { ApplyLeaveDialog } from "@/features/leave/components/apply-leave-dialog";
import { LeaveStatusBadge } from "@/features/leave/components/leave-status-badge";
import { RejectLeaveDialog } from "@/features/leave/components/reject-leave-dialog";
import {
  type LeaveApplicationStatus,
  leaveApplicationStatusLabels,
  leaveApplicationStatusValues,
} from "@/features/leave/schemas/leave-schemas";

const PAGE_SIZE = 20;

export function LeaveApplicationsPage() {
  const [status, setStatus] = useState<LeaveApplicationStatus | "all">("pending");
  const [skip, setSkip] = useState(0);
  const [applyOpen, setApplyOpen] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<string | null>(null);

  const { data, isLoading, isError } = useLeaveApplications({
    status: status === "all" ? undefined : status,
    skip,
    limit: PAGE_SIZE,
  });
  const { data: employees } = useEmployeesList({ limit: 200 });
  const { data: leaveTypes } = useLeaveTypes();
  const approveLeave = useApproveLeave();

  const employeeName = (id: string) => employees?.items.find((e) => e.id === id)?.full_name ?? id;
  const leaveTypeName = (id: string) => leaveTypes?.find((lt) => lt.id === id)?.name ?? id;

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Leave Applications</h1>
          <p className="mt-1 text-muted-foreground">
            Review, approve, and track employee leave requests.
          </p>
        </div>
        <Button onClick={() => setApplyOpen(true)}>
          <Plus className="h-4 w-4" />
          Apply for leave
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Select
            value={status}
            onValueChange={(value) => {
              setStatus(value as LeaveApplicationStatus | "all");
              setSkip(0);
            }}
          >
            <SelectTrigger className="sm:w-48">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {leaveApplicationStatusValues.map((s) => (
                <SelectItem key={s} value={s}>
                  {leaveApplicationStatusLabels[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load leave applications. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No leave applications found for this filter.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Leave type</TableHead>
                  <TableHead>Dates</TableHead>
                  <TableHead>Days</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((application) => (
                  <TableRow key={application.id}>
                    <TableCell className="font-medium">{employeeName(application.employee_id)}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {leaveTypeName(application.leave_type_id)}
                    </TableCell>
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
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => approveLeave.mutate(application.id)}
                            disabled={approveLeave.isPending}
                          >
                            Approve
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setRejectTarget(application.id)}
                          >
                            Reject
                          </Button>
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} applications)
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

      <ApplyLeaveDialog open={applyOpen} onOpenChange={setApplyOpen} />
      <RejectLeaveDialog
        open={!!rejectTarget}
        onOpenChange={(open) => !open && setRejectTarget(null)}
        applicationId={rejectTarget}
      />
    </div>
  );
}
