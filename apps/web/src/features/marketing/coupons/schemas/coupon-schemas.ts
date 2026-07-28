import { z } from "zod";

export const couponDiscountTypeValues = ["percentage", "fixed_amount"] as const;
export type CouponDiscountType = (typeof couponDiscountTypeValues)[number];

export const couponDiscountTypeLabels: Record<CouponDiscountType, string> = {
  percentage: "Percentage",
  fixed_amount: "Fixed Amount",
};

export const couponFormSchema = z.object({
  code: z.string().min(2, "Code is required."),
  campaignId: z.string().optional().or(z.literal("")),
  description: z.string().optional().or(z.literal("")),
  discountType: z.enum(couponDiscountTypeValues),
  discountValue: z.coerce.number().gt(0, "Discount value must be greater than zero."),
  maxDiscountAmount: z.coerce.number().min(0).optional(),
  minOrderAmount: z.coerce.number().min(0).default(0),
  usageLimitTotal: z.coerce.number().min(1).optional(),
  usageLimitPerCustomer: z.coerce.number().min(1).default(1),
  validFrom: z.string().min(1, "Valid-from date is required."),
  validUntil: z.string().min(1, "Valid-until date is required."),
});
export type CouponFormValues = z.infer<typeof couponFormSchema>;
