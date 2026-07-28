import { z } from "zod";

export const leaveApplicationStatusValues = ["pending", "approved", "rejected", "cancelled"] as const;
export type LeaveApplicationStatus = (typeof leaveApplicationStatusValues)[number];

export const leaveApplicationStatusLabels: Record<LeaveApplicationStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export const leaveTypeFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  code: z.string().min(1, "Code is required."),
  annualQuota: z.coerce.number().min(0, "Quota must be zero or more."),
  isPaid: z.boolean(),
  carryForwardAllowed: z.boolean(),
  maxCarryForwardDays: z.coerce.number().optional(),
});
export type LeaveTypeFormValues = z.infer<typeof leaveTypeFormSchema>;

export const leaveApplicationFormSchema = z.object({
  employeeId: z.string().min(1, "Employee is required."),
  leaveTypeId: z.string().min(1, "Leave type is required."),
  startDate: z.string().min(1, "Start date is required."),
  endDate: z.string().min(1, "End date is required."),
  reason: z.string().min(2, "Reason is required."),
});
export type LeaveApplicationFormValues = z.infer<typeof leaveApplicationFormSchema>;
