import { z } from "zod";

export const labDifficultyValues = ["easy", "medium", "hard", "insane"] as const;
export type LabDifficulty = (typeof labDifficultyValues)[number];

export const labDifficultyLabels: Record<LabDifficulty, string> = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
  insane: "Insane",
};

export const labFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  slug: z
    .string()
    .min(2, "Slug is required.")
    .regex(/^[a-z0-9-]+$/, "Slug may only contain lowercase letters, numbers, and hyphens."),
  description: z.string().optional().or(z.literal("")),
  category: z.string().min(2, "Category is required."),
  difficulty: z.enum(labDifficultyValues),
  environmentImage: z.string().min(1, "Environment image is required."),
  points: z.string().min(1, "Points is required."),
  defaultDurationMinutes: z.string().min(1, "Duration is required."),
});
export type LabFormValues = z.infer<typeof labFormSchema>;
