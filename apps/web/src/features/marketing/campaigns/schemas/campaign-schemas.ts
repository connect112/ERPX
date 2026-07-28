import { z } from "zod";

export const campaignChannelValues = [
  "email",
  "sms",
  "social_media",
  "google_ads",
  "whatsapp",
  "event",
  "other",
] as const;
export type CampaignChannel = (typeof campaignChannelValues)[number];

export const campaignChannelLabels: Record<CampaignChannel, string> = {
  email: "Email",
  sms: "SMS",
  social_media: "Social Media",
  google_ads: "Google Ads",
  whatsapp: "WhatsApp",
  event: "Event",
  other: "Other",
};

export const campaignStatusValues = [
  "draft",
  "scheduled",
  "active",
  "paused",
  "completed",
  "cancelled",
] as const;
export type CampaignStatus = (typeof campaignStatusValues)[number];

export const campaignStatusLabels: Record<CampaignStatus, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  active: "Active",
  paused: "Paused",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const campaignFormSchema = z.object({
  campaignCode: z.string().min(1, "Code is required."),
  name: z.string().min(2, "Name is required."),
  channel: z.enum(campaignChannelValues),
  startDate: z.string().min(1, "Start date is required."),
  endDate: z.string().optional().or(z.literal("")),
  budgetAmount: z.coerce.number().min(0).optional(),
  actualSpend: z.coerce.number().min(0).optional(),
  targetAudience: z.string().optional().or(z.literal("")),
  goal: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type CampaignFormValues = z.infer<typeof campaignFormSchema>;
