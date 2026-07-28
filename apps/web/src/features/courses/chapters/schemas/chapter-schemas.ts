import { z } from "zod";

export const chapterFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  description: z.string().optional().or(z.literal("")),
  orderIndex: z.string().min(1, "Order is required."),
});
export type ChapterFormValues = z.infer<typeof chapterFormSchema>;
