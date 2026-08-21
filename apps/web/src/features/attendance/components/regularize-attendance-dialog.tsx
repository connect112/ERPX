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
import type { AttendanceRecordPublic } from "@/features/attendance/api/attendance-api";
import { useRegularizeAttendance } from "@/features/attendance/api/attendance-hooks";
import {
  type RegularizeAttendanceFormValues,
  attendanceStatusLabels,
  attendanceStatusValues,
  regularizeAttendanceFormSchema,
} from "@/features/attendance/schemas/attendance-schemas";

interface RegularizeAttendanceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  record: AttendanceRecordPublic | null;
}

export function RegularizeAttendanceDialog({
  open,
  onOpenChange,
  record,
}: RegularizeAttendanceDialogProps) {
  const regularize = useRegularizeAttendance();

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RegularizeAttendanceFormValues>({
    resolver: zodResolver(regularizeAttendanceFormSchema),
    defaultValues: { checkInTime: "", checkOutTime: "", status: "", regularizationReason: "" },
  });

  useEffect(() => {
    if (open && record) {
      reset({
        checkInTime: record.check_in_time ?? "",
        checkOutTime: record.check_out_time ?? "",
        status: "",
        regularizationReason: "",
      });
    }
  }, [open, record, reset]);

  const onSubmit = (values: RegularizeAttendanceFormValues) => {
    if (!record) return;
    regularize.mutate(
      {
        id: record.id,
        payload: {
          check_in_time: values.checkInTime || undefined,
          check_out_time: values.checkOutTime || undefined,
          status: values.status || undefined,
          regularization_reason: values.regularizationReason,
        },
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Regularize attendance</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="checkInTime">Check-in time</Label>
              <Input id="checkInTime" type="datetime-local" {...register("checkInTime")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="checkOutTime">Check-out time</Label>
              <Input id="checkOutTime" type="datetime-local" {...register("checkOutTime")} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="status">Status</Label>
            <Controller
              control={control}
              name="status"
              render={({ field }) => (
                <Select value={field.value || undefined} onValueChange={field.onChange}>
                  <SelectTrigger id="status">
                    <SelectValue placeholder="Keep current status" />
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
          <div className="space-y-2">
            <Label htmlFor="regularizationReason" required>Reason</Label>
            <Textarea id="regularizationReason" rows={2} {...register("regularizationReason")} />
            {errors.regularizationReason && (
              <p className="text-sm text-destructive">{errors.regularizationReason.message}</p>
            )}
          </div>

          {regularize.isError && (
            <p className="text-sm text-destructive">
              {(regularize.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={regularize.isPending}>
              {regularize.isPending ? "Saving..." : "Regularize"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
