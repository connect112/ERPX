import { z } from "zod";

export const referralStatusValues = ["pending", "converted", "rewarded", "expired", "rejected"] as const;
export type ReferralStatus = (typeof referralStatusValues)[number];

export const referralStatusLabels: Record<ReferralStatus, string> = {
  pending: "Pending",
  converted: "Converted",
  rewarded: "Rewarded",
  expired: "Expired",
  rejected: "Rejected",
};

export const referralProgramFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  code: z.string().min(1, "Code is required."),
  referrerRewardAmount: z.coerce.number().min(0, "Must be zero or more."),
  refereeDiscountAmount: z.coerce.number().min(0).default(0),
  maxReferralsPerReferrer: z.coerce.number().min(1).optional(),
  validFrom: z.string().min(1, "Valid-from date is required."),
  validUntil: z.string().optional().or(z.literal("")),
});
export type ReferralProgramFormValues = z.infer<typeof referralProgramFormSchema>;

export const referralFormSchema = z.object({
  referralProgramId: z.string().min(1, "Program is required."),
  referrerStudentId: z.string().optional().or(z.literal("")),
  refereeName: z.string().min(2, "Referee name is required."),
  refereeEmail: z.string().email("Enter a valid email address.").optional().or(z.literal("")),
  refereePhone: z.string().optional().or(z.literal("")),
});
export type ReferralFormValues = z.infer<typeof referralFormSchema>;
