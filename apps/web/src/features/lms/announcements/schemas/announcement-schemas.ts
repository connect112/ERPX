import { z } from "zod";

export const announcementFormSchema = z.object({
  courseId: z.string().optional().or(z.literal("")),
  title: z.string().min(2, "Title is required."),
  body: z.string().min(1, "Body is required."),
});
export type AnnouncementFormValues = z.infer<typeof announcementFormSchema>;
