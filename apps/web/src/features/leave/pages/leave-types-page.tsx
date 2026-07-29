import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useId, useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCreateLeaveType, useLeaveTypes } from "@/features/leave/api/leave-hooks";
import { type LeaveTypeFormValues, leaveTypeFormSchema } from "@/features/leave/schemas/leave-schemas";

const emptyValues: LeaveTypeFormValues = {
  name: "",
  code: "",
  annualQuota: 0,
  isPaid: true,
  carryForwardAllowed: false,
  maxCarryForwardDays: undefined,
};

export function LeaveTypesPage() {
  const { data: leaveTypes, isLoading, isError } = useLeaveTypes();
  const createLeaveType = useCreateLeaveType();
  const isPaidId = useId();
  const carryForwardId = useId();
  const [formOpen, setFormOpen] = useState(false);

  const {
    register,
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<LeaveTypeFormValues>({
    resolver: zodResolver(leaveTypeFormSchema),
    defaultValues: emptyValues,
  });

  const carryForwardAllowed = watch("carryForwardAllowed");

  const onSubmit = (values: LeaveTypeFormValues) => {
    createLeaveType.mutate(
      {
        name: values.name,
        code: values.code,
        annual_quota: values.annualQuota,
        is_paid: values.isPaid,
        carry_forward_allowed: values.carryForwardAllowed,
        max_carry_forward_days: values.carryForwardAllowed ? values.maxCarryForwardDays : undefined,
      },
      {
        onSuccess: () => {
          setFormOpen(false);
          reset(emptyValues);
        },
      }
    );
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Leave Types</h1>
          <p className="mt-1 text-muted-foreground">
            Configure the leave categories available to your organization.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New leave type
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All leave types</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && <p className="text-sm text-destructive">Failed to load leave types.</p>}
          {!isLoading && !isError && (leaveTypes?.length ?? 0) === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">No leave types yet.</p>
          )}
          {!isLoading && !isError && (leaveTypes?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Annual quota</TableHead>
                  <TableHead>Paid</TableHead>
                  <TableHead>Carry forward</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leaveTypes?.map((lt) => (
                  <TableRow key={lt.id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">{lt.code}</TableCell>
                    <TableCell className="font-medium">{lt.name}</TableCell>
                    <TableCell className="text-muted-foreground">{lt.annual_quota}</TableCell>
                    <TableCell className="text-muted-foreground">{lt.is_paid ? "Yes" : "No"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {lt.carry_forward_allowed
                        ? `Up to ${lt.max_carry_forward_days ?? "—"} days`
                        : "No"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={lt.is_active ? "success" : "secondary"}>
                        {lt.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New leave type</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" {...register("name")} />
                {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="code">Code</Label>
                <Input id="code" {...register("code")} />
                {errors.code && <p className="text-sm text-destructive">{errors.code.message}</p>}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="annualQuota">Annual quota (days)</Label>
              <Input id="annualQuota" type="number" step="0.5" {...register("annualQuota")} />
              {errors.annualQuota && (
                <p className="text-sm text-destructive">{errors.annualQuota.message}</p>
              )}
            </div>
            <label htmlFor={isPaidId} className="flex items-center gap-2 text-sm">
              <Controller
                control={control}
                name="isPaid"
                render={({ field }) => (
                  <input
                    id={isPaidId}
                    type="checkbox"
                    className="h-4 w-4 rounded border-input"
                    checked={field.value}
                    onChange={(e) => field.onChange(e.target.checked)}
                  />
                )}
              />
              Paid leave
            </label>
            <label htmlFor={carryForwardId} className="flex items-center gap-2 text-sm">
              <Controller
                control={control}
                name="carryForwardAllowed"
                render={({ field }) => (
                  <input
                    id={carryForwardId}
                    type="checkbox"
                    className="h-4 w-4 rounded border-input"
                    checked={field.value}
                    onChange={(e) => field.onChange(e.target.checked)}
                  />
                )}
              />
              Allow carry forward
            </label>
            {carryForwardAllowed && (
              <div className="space-y-2">
                <Label htmlFor="maxCarryForwardDays">Max carry forward days</Label>
                <Input id="maxCarryForwardDays" type="number" {...register("maxCarryForwardDays")} />
              </div>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createLeaveType.isPending}>
                {createLeaveType.isPending ? "Saving..." : "Create leave type"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
