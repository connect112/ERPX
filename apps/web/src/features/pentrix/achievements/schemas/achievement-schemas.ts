import { z } from "zod";

export const achievementCriteriaTypeValues = ["challenges_solved", "points_threshold"] as const;
export type AchievementCriteriaType = (typeof achievementCriteriaTypeValues)[number];

export const achievementCriteriaTypeLabels: Record<AchievementCriteriaType, string> = {
  challenges_solved: "Challenges Solved",
  points_threshold: "Points Threshold",
};

export const achievementFormSchema = z.object({
  name: z.string().min(2, "Name is required."),
  description: z.string().optional().or(z.literal("")),
  criteriaType: z.enum(achievementCriteriaTypeValues),
  criteriaValue: z.string().min(1, "Criteria value is required."),
});
export type AchievementFormValues = z.infer<typeof achievementFormSchema>;
