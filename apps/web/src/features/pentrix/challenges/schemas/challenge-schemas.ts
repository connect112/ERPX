import { z } from "zod";

import { labDifficultyValues } from "@/features/pentrix/labs/schemas/lab-schemas";

export const challengeFormSchema = z.object({
  labId: z.string().optional().or(z.literal("")),
  title: z.string().min(2, "Title is required."),
  description: z.string().min(2, "Description is required."),
  category: z.string().min(2, "Category is required."),
  difficulty: z.enum(labDifficultyValues),
  points: z.string().min(1, "Points is required."),
});
export type ChallengeFormValues = z.infer<typeof challengeFormSchema>;
