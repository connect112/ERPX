import { z } from "zod";

export const leadSourceValues = [
  "website",
  "referral",
  "social_media",
  "walk_in",
  "advertisement",
  "event",
  "other",
] as const;
export type LeadSource = (typeof leadSourceValues)[number];

export const leadStatusValues = ["new", "contacted", "qualified", "converted", "lost"] as const;
export type LeadStatus = (typeof leadStatusValues)[number];

export const leadStatusLabels: Record<LeadStatus, string> = {
  new: "New",
  contacted: "Contacted",
  qualified: "Qualified",
  converted: "Converted",
  lost: "Lost",
};

export const leadSourceLabels: Record<LeadSource, string> = {
  website: "Website",
  referral: "Referral",
  social_media: "Social Media",
  walk_in: "Walk-in",
  advertisement: "Advertisement",
  event: "Event",
  other: "Other",
};

export const leadStatusTransitions: Record<LeadStatus, LeadStatus[]> = {
  new: ["contacted", "lost"],
  contacted: ["qualified", "lost"],
  qualified: ["converted", "lost"],
  converted: [],
  lost: ["new"],
};

export const leadFormSchema = z.object({
  fullName: z.string().min(2, "Full name is required."),
  email: z.string().email("Enter a valid email address.").optional().or(z.literal("")),
  phone: z.string().optional().or(z.literal("")),
  source: z.enum(leadSourceValues),
  assignedToUserId: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type LeadFormValues = z.infer<typeof leadFormSchema>;

export const leadStatusChangeSchema = z
  .object({
    status: z.enum(leadStatusValues),
    lostReason: z.string().optional().or(z.literal("")),
  })
  .refine((data) => data.status !== "lost" || !!data.lostReason?.trim(), {
    message: "A reason is required when marking a lead as lost.",
    path: ["lostReason"],
  });
export type LeadStatusChangeValues = z.infer<typeof leadStatusChangeSchema>;
