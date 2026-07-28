import { z } from "zod";

export const resourceTypeValues = ["video", "note", "pdf", "document", "link", "other"] as const;
export type ResourceType = (typeof resourceTypeValues)[number];

export const resourceTypeLabels: Record<ResourceType, string> = {
  video: "Video",
  note: "Note",
  pdf: "PDF",
  document: "Document",
  link: "Link",
  other: "Other",
};

export const resourceFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  resourceType: z.enum(resourceTypeValues),
  fileUrl: z.string().min(1, "File URL is required."),
  isDownloadable: z.boolean(),
});
export type ResourceFormValues = z.infer<typeof resourceFormSchema>;
