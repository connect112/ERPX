import type { ReplyRecord, ReplyStatus, Triage } from "@/features/social-media/api/social-media-api";

export const CATEGORY_LABEL: Record<Triage["category"], string> = {
  enquiry: "Enquiry",
  complaint: "Complaint",
  question: "Question",
  thanks: "Thanks",
  spam: "Possible spam",
  other: "Other",
};

export const REPLY_STATUS_LABEL: Record<ReplyStatus, string> = {
  pending: "Sending",
  sent: "Sent",
  failed: "Not sent",
  unknown: "Unclear",
};

export const REPLY_STATUS_VARIANT: Record<ReplyStatus, "success" | "destructive" | "warning" | "secondary"> = {
  pending: "secondary",
  sent: "success",
  failed: "destructive",
  unknown: "warning",
};

export const SOURCE_LABEL: Record<ReplyRecord["source"], string> = {
  typed: "Written by a person",
  suggestion_edited: "AI draft, edited by a person",
  suggestion_unchanged: "AI draft, confirmed by a person",
};
