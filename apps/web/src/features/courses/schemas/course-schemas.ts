import { z } from "zod";

export const courseLevelValues = ["beginner", "intermediate", "advanced"] as const;
export type CourseLevel = (typeof courseLevelValues)[number];

export const courseLevelLabels: Record<CourseLevel, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};

export const courseFormSchema = z.object({
  categoryId: z.string().optional().or(z.literal("")),
  title: z.string().min(2, "Title is required."),
  slug: z
    .string()
    .min(2, "Slug is required.")
    .regex(/^[a-z0-9-]+$/, "Slug may only contain lowercase letters, numbers, and hyphens."),
  shortDescription: z.string().optional().or(z.literal("")),
  description: z.string().optional().or(z.literal("")),
  thumbnailUrl: z.string().optional().or(z.literal("")),
  level: z.enum(courseLevelValues),
  durationHours: z.string().optional().or(z.literal("")),
  price: z.string().optional().or(z.literal("")),
});
export type CourseFormValues = z.infer<typeof courseFormSchema>;
