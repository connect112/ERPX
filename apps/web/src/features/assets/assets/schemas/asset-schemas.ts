import { z } from "zod";
import { coerceNumber } from "@/lib/zod-helpers";

import { depreciationMethodValues } from "@/features/assets/categories/schemas/asset-category-schemas";

export const assetStatusValues = ["in_use", "in_storage", "under_maintenance", "disposed"] as const;
export type AssetStatus = (typeof assetStatusValues)[number];

export const assetStatusLabels: Record<AssetStatus, string> = {
  in_use: "In Use",
  in_storage: "In Storage",
  under_maintenance: "Under Maintenance",
  disposed: "Disposed",
};

export const assetFormSchema = z.object({
  assetCode: z.string().min(1, "Asset code is required."),
  name: z.string().min(2, "Name is required."),
  categoryId: z.string().optional().or(z.literal("")),
  assignedToEmployeeId: z.string().optional().or(z.literal("")),
  assetAccountId: z.string().min(1, "Asset account is required."),
  accumulatedDepreciationAccountId: z.string().min(1, "Accumulated depreciation account is required."),
  depreciationExpenseAccountId: z.string().min(1, "Depreciation expense account is required."),
  description: z.string().optional().or(z.literal("")),
  location: z.string().optional().or(z.literal("")),
  purchaseDate: z.string().min(1, "Purchase date is required."),
  purchaseCost: coerceNumber().gt(0, "Purchase cost must be greater than zero."),
  salvageValue: coerceNumber().min(0, "Must be zero or more.").default(0),
  usefulLifeYears: coerceNumber().min(1, "Must be at least 1 year."),
  depreciationMethod: z.enum(depreciationMethodValues),
  notes: z.string().optional().or(z.literal("")),
});
export type AssetFormValues = z.infer<typeof assetFormSchema>;

export const assetEditFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  categoryId: z.string().optional().or(z.literal("")),
  assignedToEmployeeId: z.string().optional().or(z.literal("")),
  description: z.string().optional().or(z.literal("")),
  location: z.string().optional().or(z.literal("")),
  status: z.enum(assetStatusValues),
  notes: z.string().optional().or(z.literal("")),
});
export type AssetEditFormValues = z.infer<typeof assetEditFormSchema>;

export const disposeAssetFormSchema = z.object({
  disposalDate: z.string().min(1, "Disposal date is required."),
  disposalAmount: coerceNumber().min(0, "Must be zero or more."),
  cashAccountId: z.string().min(1, "Cash account is required."),
  gainLossAccountId: z.string().min(1, "Gain/loss account is required."),
});
export type DisposeAssetFormValues = z.infer<typeof disposeAssetFormSchema>;
