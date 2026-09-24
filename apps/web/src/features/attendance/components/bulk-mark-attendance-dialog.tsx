import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useFieldArray, useForm } from "react-hook-form";

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
import { useBulkMarkAttendance } from "@/features/attendance/api/attendance-hooks";
import {
  type BulkMarkAttendanceFormValues,
  attendanceStatusLabels,
  attendanceStatusValues,
  bulkMarkAttendanceFormSchema,
} from "@/features/attendance/schemas/attendance-schemas";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";

interface BulkMarkAttendanceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultEmployeeId?: string;
}

const emptyValues: BulkMarkAttendanceFormValues = {
  employeeId: "",
  startDate: "",
  endDate: "",
  defaultStatus: "present",
  autoWeekOffSundays: true,
  exceptions: [],
};

export function BulkMarkAttendanceDialog({
  open,
  onOpenChange,
  defaultEmployeeId,
}: BulkMarkAttendanceDialogProps) {
  const bulkMark = useBulkMarkAttendance();
  const { data: employees } = useEmployeesList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<BulkMarkAttendanceFormValues>({
    resolver: zodResolver(bulkMarkAttendanceFormSchema),
    defaultValues: emptyValues,
  });
  const { fields, append, remove } = useFieldArray({ control, name: "exceptions" });

  useEffect(() => {
    if (open) {
      reset({ ...emptyValues, employeeId: defaultEmployeeId ?? "" });
    }
  }, [open, defaultEmployeeId, reset]);

  const onSubmit = (values: BulkMarkAttendanceFormValues) => {
    bulkMark.mutate(
      {
        employee_id: values.employeeId,
        start_date: values.startDate,
        end_date: values.endDate,
        default_status: values.defaultStatus,
        auto_week_off_sundays: values.autoWeekOffSundays,
        exceptions: values.exceptions.map((e) => ({
          start_date: e.startDate,
          end_date: e.endDate,
          status: e.status,
          remarks: e.remarks || undefined,
        })),
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Bulk mark attendance</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <p className="text-sm text-muted-foreground">
            Marks a whole date range in one go — e.g. backfilling history predating this
            employee's ERPX record. Sundays are automatically Week Off unless you uncheck that
            below. Add an exception below to override a block of days (e.g. an extended-leave
            stretch) with a different status.
          </p>
          <div className="space-y-2">
            <Label htmlFor="employeeId">Employee</Label>
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
              <Label htmlFor="startDate">Start date</Label>
              <Input id="startDate" type="date" {...register("startDate")} />
              {errors.startDate && (
                <p className="text-sm text-destructive">{errors.startDate.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="endDate">End date</Label>
              <Input id="endDate" type="date" {...register("endDate")} />
              {errors.endDate && <p className="text-sm text-destructive">{errors.endDate.message}</p>}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="defaultStatus">Default status for the whole range</Label>
            <Controller
              control={control}
              name="defaultStatus"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="defaultStatus">
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
          <label htmlFor="autoWeekOffSundays" className="flex items-center gap-2 text-sm">
            <Controller
              control={control}
              name="autoWeekOffSundays"
              render={({ field }) => (
                <input
                  id="autoWeekOffSundays"
                  type="checkbox"
                  className="h-4 w-4 rounded border-input"
                  checked={field.value}
                  onChange={(e) => field.onChange(e.target.checked)}
                />
              )}
            />
            Automatically mark Sundays as Week Off
          </label>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Exceptions
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => append({ startDate: "", endDate: "", status: "absent", remarks: "" })}
              >
                Add exception
              </Button>
            </div>
            {fields.map((field, index) => (
              <div key={field.id} className="space-y-2 rounded-md border p-3">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor={`exceptions.${index}.startDate`}>Start date</Label>
                    <Input
                      id={`exceptions.${index}.startDate`}
                      type="date"
                      {...register(`exceptions.${index}.startDate` as const)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`exceptions.${index}.endDate`}>End date</Label>
                    <Input
                      id={`exceptions.${index}.endDate`}
                      type="date"
                      {...register(`exceptions.${index}.endDate` as const)}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`exceptions.${index}.status`}>Status</Label>
                  <Controller
                    control={control}
                    name={`exceptions.${index}.status` as const}
                    render={({ field: statusField }) => (
                      <Select value={statusField.value} onValueChange={statusField.onChange}>
                        <SelectTrigger id={`exceptions.${index}.status`}>
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
                <Button type="button" variant="ghost" size="sm" onClick={() => remove(index)}>
                  Remove
                </Button>
              </div>
            ))}
          </div>

          {bulkMark.isError && (
            <p className="text-sm text-destructive">
              {(bulkMark.error as { response?: { data?: { error?: { message?: string } } } })?.response
                ?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={bulkMark.isPending}>
              {bulkMark.isPending ? "Marking..." : "Mark attendance"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
