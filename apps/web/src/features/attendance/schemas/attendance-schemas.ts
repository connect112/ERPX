import { z } from "zod";

export const attendanceStatusValues = [
  "present",
  "absent",
  "half_day",
  "on_leave",
  "holiday",
  "week_off",
] as const;
export type AttendanceStatus = (typeof attendanceStatusValues)[number];

export const attendanceStatusLabels: Record<AttendanceStatus, string> = {
  present: "Present",
  absent: "Absent",
  half_day: "Half Day",
  on_leave: "On Leave",
  holiday: "Holiday",
  week_off: "Week Off",
};

export const markAttendanceFormSchema = z.object({
  employeeId: z.string().min(1, "Employee is required."),
  attendanceDate: z.string().min(1, "Date is required."),
  status: z.enum(attendanceStatusValues),
  remarks: z.string().optional().or(z.literal("")),
});
export type MarkAttendanceFormValues = z.infer<typeof markAttendanceFormSchema>;

export const bulkMarkAttendanceFormSchema = z.object({
  employeeId: z.string().min(1, "Employee is required."),
  startDate: z.string().min(1, "Start date is required."),
  endDate: z.string().min(1, "End date is required."),
  defaultStatus: z.enum(attendanceStatusValues),
  autoWeekOffSundays: z.boolean(),
  exceptions: z.array(
    z.object({
      startDate: z.string().min(1, "Start date is required."),
      endDate: z.string().min(1, "End date is required."),
      status: z.enum(attendanceStatusValues),
      remarks: z.string().optional().or(z.literal("")),
    })
  ),
});
export type BulkMarkAttendanceFormValues = z.infer<typeof bulkMarkAttendanceFormSchema>;

export const regularizeAttendanceFormSchema = z.object({
  checkInTime: z.string().optional().or(z.literal("")),
  checkOutTime: z.string().optional().or(z.literal("")),
  status: z.union([z.enum(attendanceStatusValues), z.literal("")]).optional(),
  regularizationReason: z.string().min(1, "Reason is required."),
});
export type RegularizeAttendanceFormValues = z.infer<typeof regularizeAttendanceFormSchema>;
