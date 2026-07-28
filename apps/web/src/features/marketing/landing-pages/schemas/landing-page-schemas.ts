import { z } from "zod";

export const landingPageStatusValues = ["draft", "published", "archived"] as const;
export type LandingPageStatus = (typeof landingPageStatusValues)[number];

export const landingPageStatusLabels: Record<LandingPageStatus, string> = {
  draft: "Draft",
  published: "Published",
  archived: "Archived",
};

export const landingPageFormSchema = z.object({
  slug: z
    .string()
    .min(2, "Slug is required.")
    .regex(/^[a-z0-9-]+$/, "Use lowercase letters, numbers, and hyphens only."),
  title: z.string().min(2, "Title is required."),
  campaignId: z.string().optional().or(z.literal("")),
  metaDescription: z.string().optional().or(z.literal("")),
  content: z.string().min(1, "Content is required."),
});
export type LandingPageFormValues = z.infer<typeof landingPageFormSchema>;
