import { z } from "zod";

export const lessonContentTypeValues = ["video", "text", "document", "quiz"] as const;
export type LessonContentType = (typeof lessonContentTypeValues)[number];

export const lessonContentTypeLabels: Record<LessonContentType, string> = {
  video: "Video",
  text: "Text",
  document: "Document",
  quiz: "Quiz",
};

export const lessonFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  contentType: z.enum(lessonContentTypeValues),
  videoUrl: z.string().optional().or(z.literal("")),
  contentText: z.string().optional().or(z.literal("")),
  durationMinutes: z.string().optional().or(z.literal("")),
  orderIndex: z.string().min(1, "Order is required."),
  isPreview: z.boolean(),
});
export type LessonFormValues = z.infer<typeof lessonFormSchema>;
