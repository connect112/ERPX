import { z } from "zod";

export const ticketPriorityValues = ["low", "medium", "high", "urgent"] as const;
export type TicketPriority = (typeof ticketPriorityValues)[number];

export const ticketPriorityLabels: Record<TicketPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

export const ticketStatusValues = ["open", "in_progress", "on_hold", "resolved", "closed"] as const;
export type TicketStatus = (typeof ticketStatusValues)[number];

export const ticketStatusLabels: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In Progress",
  on_hold: "On Hold",
  resolved: "Resolved",
  closed: "Closed",
};

export const ticketFormSchema = z.object({
  ticketNumber: z.string().min(1, "Ticket number is required."),
  projectId: z.string().optional().or(z.literal("")),
  subject: z.string().min(2, "Subject is required."),
  description: z.string().min(2, "Description is required."),
  priority: z.enum(ticketPriorityValues),
  assignedToEmployeeId: z.string().optional().or(z.literal("")),
  raisedByContactName: z.string().optional().or(z.literal("")),
  slaDueAt: z.string().optional().or(z.literal("")),
});
export type TicketFormValues = z.infer<typeof ticketFormSchema>;

export const ticketCommentFormSchema = z.object({
  commentText: z.string().min(1, "Comment is required."),
  isInternal: z.boolean(),
});
export type TicketCommentFormValues = z.infer<typeof ticketCommentFormSchema>;
