import { z } from "zod";

export const threadFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  body: z.string().min(1, "Body is required."),
});
export type ThreadFormValues = z.infer<typeof threadFormSchema>;

export const replyFormSchema = z.object({
  body: z.string().min(1, "Reply cannot be empty."),
});
export type ReplyFormValues = z.infer<typeof replyFormSchema>;
