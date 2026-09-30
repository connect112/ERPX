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

export const regularizeAttendanceFormSchema = z.object({
  checkInTime: z.string().optional().or(z.literal("")),
  checkOutTime: z.string().optional().or(z.literal("")),
  status: z.union([z.enum(attendanceStatusValues), z.literal("")]).optional(),
  regularizationReason: z.string().min(1, "Reason is required."),
});
export type RegularizeAttendanceFormValues = z.infer<typeof regularizeAttendanceFormSchema>;
