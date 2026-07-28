import { z } from "zod";

export const approvalRequestStatusValues = ["pending", "approved", "rejected", "cancelled"] as const;
export type ApprovalRequestStatus = (typeof approvalRequestStatusValues)[number];

export const approvalRequestStatusLabels: Record<ApprovalRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
};

export const workflowStepInputSchema = z.object({
  stepOrder: z.number().int().min(1),
  approverRoleId: z.string().min(1, "Select an approver role."),
  name: z.string().optional().or(z.literal("")),
});

export const workflowFormSchema = z.object({
  entityType: z
    .string()
    .min(1, "Entity type is required.")
    .regex(/^[a-z][a-z0-9_]*$/, "Use lowercase letters, numbers, and underscores only."),
  name: z.string().min(2, "Name is required."),
  description: z.string().optional().or(z.literal("")),
  steps: z.array(workflowStepInputSchema).min(1, "Add at least one approval step."),
});
export type WorkflowFormValues = z.infer<typeof workflowFormSchema>;
