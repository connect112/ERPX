import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
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
import { Textarea } from "@/components/ui/textarea";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import { useApplyLeave } from "@/features/leave/api/leave-hooks";
import { useLeaveTypes } from "@/features/leave/api/leave-hooks";
import { type LeaveApplicationFormValues, leaveApplicationFormSchema } from "@/features/leave/schemas/leave-schemas";

interface ApplyLeaveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultEmployeeId?: string;
}

const emptyValues: LeaveApplicationFormValues = {
  employeeId: "",
  leaveTypeId: "",
  startDate: "",
  endDate: "",
  reason: "",
};

export function ApplyLeaveDialog({ open, onOpenChange, defaultEmployeeId }: ApplyLeaveDialogProps) {
  const applyLeave = useApplyLeave();
  const { data: employees } = useEmployeesList({ limit: 200 });
  const { data: leaveTypes } = useLeaveTypes(true);

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<LeaveApplicationFormValues>({
    resolver: zodResolver(leaveApplicationFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset({ ...emptyValues, employeeId: defaultEmployeeId ?? "" });
    }
  }, [open, defaultEmployeeId, reset]);

  const onSubmit = (values: LeaveApplicationFormValues) => {
    applyLeave.mutate(
      {
        employee_id: values.employeeId,
        leave_type_id: values.leaveTypeId,
        start_date: values.startDate,
        end_date: values.endDate,
        reason: values.reason,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Apply for leave</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="employeeId" required>Employee</Label>
            <Controller
              control={control}
              name="employeeId"
              render={({ field }) => (
                <Select
                  value={field.value || undefined}
                  onValueChange={field.onChange}
                  disabled={!!defaultEmployeeId}
                >
                  <SelectTrigger id="employeeId">
                    <SelectValue placeholder="Select employee" />
                  </SelectTrigger>
                  <SelectContent>
                    {employees?.items.map((e) => (
                      <SelectItem key={e.id} value={e.id}>
                        {e.full_name} ({e.employee_code})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.employeeId && (
              <p className="text-sm text-destructive">{errors.employeeId.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="leaveTypeId" required>Leave type</Label>
            <Controller
              control={control}
              name="leaveTypeId"
              render={({ field }) => (
                <Select value={field.value || undefined} onValueChange={field.onChange}>
                  <SelectTrigger id="leaveTypeId">
                    <SelectValue placeholder="Select leave type" />
                  </SelectTrigger>
                  <SelectContent>
                    {leaveTypes?.map((lt) => (
                      <SelectItem key={lt.id} value={lt.id}>
                        {lt.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {errors.leaveTypeId && (
              <p className="text-sm text-destructive">{errors.leaveTypeId.message}</p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="startDate" required>Start date</Label>
              <Input id="startDate" type="date" {...register("startDate")} />
              {errors.startDate && (
                <p className="text-sm text-destructive">{errors.startDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="endDate" required>End date</Label>
              <Input id="endDate" type="date" {...register("endDate")} />
              {errors.endDate && <p className="text-sm text-destructive">{errors.endDate.message}</p>}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="reason" required>Reason</Label>
            <Textarea id="reason" rows={3} {...register("reason")} />
            {errors.reason && <p className="text-sm text-destructive">{errors.reason.message}</p>}
          </div>

          {applyLeave.isError && (
            <p className="text-sm text-destructive">
              {(applyLeave.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={applyLeave.isPending}>
              {applyLeave.isPending ? "Submitting..." : "Apply"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
