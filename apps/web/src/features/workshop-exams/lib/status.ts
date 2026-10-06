import type { ExamStatus } from "@/features/workshop-exams/api/workshop-exams-api";

export const examStatusBadge: Record<ExamStatus, { label: string; variant: "secondary" | "success" | "outline" }> = {
  draft: { label: "Draft", variant: "secondary" },
  open: { label: "Open", variant: "success" },
  closed: { label: "Closed", variant: "outline" },
};
