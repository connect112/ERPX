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
import { useMarkAttendance } from "@/features/attendance/api/attendance-hooks";
import {
  type MarkAttendanceFormValues,
  attendanceStatusLabels,
  attendanceStatusValues,
  markAttendanceFormSchema,
} from "@/features/attendance/schemas/attendance-schemas";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";

interface MarkAttendanceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultEmployeeId?: string;
}

const emptyValues: MarkAttendanceFormValues = {
  employeeId: "",
  attendanceDate: "",
  status: "present",
  remarks: "",
};

export function MarkAttendanceDialog({
  open,
  onOpenChange,
  defaultEmployeeId,
}: MarkAttendanceDialogProps) {
  const markAttendance = useMarkAttendance();
  const { data: employees } = useEmployeesList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<MarkAttendanceFormValues>({
    resolver: zodResolver(markAttendanceFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset({ ...emptyValues, employeeId: defaultEmployeeId ?? "" });
    }
  }, [open, defaultEmployeeId, reset]);

  const onSubmit = (values: MarkAttendanceFormValues) => {
    markAttendance.mutate(
      {
        employee_id: values.employeeId,
        attendance_date: values.attendanceDate,
        status: values.status,
        remarks: values.remarks || undefined,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Mark attendance</DialogTitle>
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
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="attendanceDate" required>Date</Label>
              <Input id="attendanceDate" type="date" {...register("attendanceDate")} />
              {errors.attendanceDate && (
                <p className="text-sm text-destructive">{errors.attendanceDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="status" required>Status</Label>
              <Controller
                control={control}
                name="status"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="status">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {attendanceStatusValues.map((s) => (
                        <SelectItem key={s} value={s}>
                          {attendanceStatusLabels[s]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="remarks">Remarks</Label>
            <Textarea id="remarks" rows={2} {...register("remarks")} />
          </div>

          {markAttendance.isError && (
            <p className="text-sm text-destructive">
              {(markAttendance.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={markAttendance.isPending}>
              {markAttendance.isPending ? "Saving..." : "Mark attendance"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
