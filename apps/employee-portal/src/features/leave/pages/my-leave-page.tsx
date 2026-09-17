import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Textarea } from "@/components/ui/textarea";
import {
  useApplyLeave,
  useCancelLeaveApplication,
  useMyLeaveApplications,
  useMyLeaveBalances,
  useMyLeaveTypes,
} from "@/features/leave/api/leave-hooks";
import type { LeaveApplicationStatus } from "@/features/leave/api/leave-api";

const statusVariant: Record<LeaveApplicationStatus, "default" | "success" | "destructive" | "outline"> = {
  pending: "default",
  approved: "success",
  rejected: "destructive",
  cancelled: "outline",
};

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function MyLeavePage() {
  const year = new Date().getFullYear();
  const { data: leaveTypes } = useMyLeaveTypes();
  const { data: applications, isLoading: applicationsLoading } = useMyLeaveApplications();
  const { data: balances, isLoading: balancesLoading } = useMyLeaveBalances(year);
  const applyLeave = useApplyLeave();
  const cancelApplication = useCancelLeaveApplication();

  const [open, setOpen] = useState(false);
  const [leaveTypeId, setLeaveTypeId] = useState("");
  const [startDate, setStartDate] = useState(todayISO());
  const [endDate, setEndDate] = useState(todayISO());
  const [reason, setReason] = useState("");

  const resetForm = () => {
    setLeaveTypeId("");
    setStartDate(todayISO());
    setEndDate(todayISO());
    setReason("");
  };

  const onSubmit = () => {
    if (!leaveTypeId || !reason.trim()) return;
    applyLeave.mutate(
      { leave_type_id: leaveTypeId, start_date: startDate, end_date: endDate, reason },
      {
        onSuccess: () => {
          setOpen(false);
          resetForm();
        },
      }
    );
  };

  const typeNames = new Map((leaveTypes ?? []).map((t) => [t.id, t.name]));

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Leave</h1>
          <p className="text-sm text-muted-foreground">
            Apply for leave and track your applications and balance.
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>Apply for leave</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Balance ({year})</CardTitle>
          <CardDescription>Days remaining per leave type this year.</CardDescription>
        </CardHeader>
        <CardContent>
          {balancesLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
            </div>
          ) : balances && balances.length > 0 ? (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {balances.map((b) => (
                <div key={b.leave_type_id} className="rounded-lg border p-3">
                  <p className="text-sm text-muted-foreground">{b.leave_type_name}</p>
                  <p className="text-xl font-semibold">{b.balance}</p>
                  <p className="text-xs text-muted-foreground">of {b.annual_quota} days</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="py-4 text-center text-sm text-muted-foreground">No leave types configured yet.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">My applications</CardTitle>
        </CardHeader>
        <CardContent>
          {applicationsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : applications && applications.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Dates</TableHead>
                  <TableHead>Days</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {applications.items.map((app) => (
                  <TableRow key={app.id}>
                    <TableCell>{typeNames.get(app.leave_type_id) ?? "—"}</TableCell>
                    <TableCell>
                      {app.start_date} – {app.end_date}
                    </TableCell>
                    <TableCell>{app.number_of_days}</TableCell>
                    <TableCell className="max-w-xs truncate">{app.reason}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant[app.status]} className="capitalize">
                        {app.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {app.status === "pending" && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={cancelApplication.isPending}
                          onClick={() => cancelApplication.mutate(app.id)}
                        >
                          Cancel
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              You haven't applied for any leave yet.
            </p>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Apply for leave</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="leaveType">Leave type</Label>
              <Select value={leaveTypeId} onValueChange={setLeaveTypeId}>
                <SelectTrigger id="leaveType">
                  <SelectValue placeholder="Select a leave type" />
                </SelectTrigger>
                <SelectContent>
                  {(leaveTypes ?? []).map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="startDate">Start date</Label>
                <Input
                  id="startDate"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="endDate">End date</Label>
                <Input
                  id="endDate"
                  type="date"
                  value={endDate}
                  min={startDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="reason">Reason</Label>
              <Textarea
                id="reason"
                rows={3}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="What's this leave for?"
              />
            </div>
            {applyLeave.isError && (
              <p className="text-sm text-destructive">
                {(applyLeave.error as { response?: { data?: { error?: { message?: string } } } })?.response
                  ?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={onSubmit}
              disabled={applyLeave.isPending || !leaveTypeId || !reason.trim()}
            >
              {applyLeave.isPending ? "Submitting..." : "Submit application"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
