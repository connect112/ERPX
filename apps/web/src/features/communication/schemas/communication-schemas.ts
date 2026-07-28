import { z } from "zod";

export const channelValues = ["email", "sms", "whatsapp"] as const;
export type Channel = (typeof channelValues)[number];

export const channelLabels: Record<Channel, string> = {
  email: "Email",
  sms: "SMS",
  whatsapp: "WhatsApp",
};

export const statusValues = ["sent", "failed"] as const;
export type CommunicationStatus = (typeof statusValues)[number];

export const statusLabels: Record<CommunicationStatus, string> = {
  sent: "Sent",
  failed: "Failed",
};

export const sendFormSchema = z
  .object({
    channel: z.enum(channelValues),
    recipient: z.string().min(1, "Recipient is required."),
    subject: z.string().optional().or(z.literal("")),
    body: z.string().min(1, "Message body is required."),
  })
  .refine((data) => data.channel !== "email" || !!data.subject, {
    message: "Subject is required for email.",
    path: ["subject"],
  });
export type SendFormValues = z.infer<typeof sendFormSchema>;
