import { z } from "zod";

export const vaptEngagementTypeValues = [
  "web_app",
  "mobile_app",
  "network",
  "cloud",
  "api",
  "red_team",
  "other",
] as const;
export type VAPTEngagementType = (typeof vaptEngagementTypeValues)[number];

export const vaptEngagementTypeLabels: Record<VAPTEngagementType, string> = {
  web_app: "Web App",
  mobile_app: "Mobile App",
  network: "Network",
  cloud: "Cloud",
  api: "API",
  red_team: "Red Team",
  other: "Other",
};

export const vaptEngagementStatusValues = [
  "scoping",
  "in_progress",
  "reporting",
  "retest",
  "closed",
] as const;
export type VAPTEngagementStatus = (typeof vaptEngagementStatusValues)[number];

export const vaptEngagementStatusLabels: Record<VAPTEngagementStatus, string> = {
  scoping: "Scoping",
  in_progress: "In Progress",
  reporting: "Reporting",
  retest: "Retest",
  closed: "Closed",
};

export const findingSeverityValues = ["critical", "high", "medium", "low", "informational"] as const;
export type FindingSeverity = (typeof findingSeverityValues)[number];

export const findingSeverityLabels: Record<FindingSeverity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  informational: "Informational",
};

export const findingStatusValues = ["open", "retesting", "fixed", "accepted_risk", "false_positive"] as const;
export type FindingStatus = (typeof findingStatusValues)[number];

export const findingStatusLabels: Record<FindingStatus, string> = {
  open: "Open",
  retesting: "Retesting",
  fixed: "Fixed",
  accepted_risk: "Accepted Risk",
  false_positive: "False Positive",
};

export const vaptEngagementFormSchema = z.object({
  scopeDescription: z.string().min(2, "Scope description is required."),
  engagementType: z.enum(vaptEngagementTypeValues),
  methodology: z.string().optional().or(z.literal("")),
  leadTesterEmployeeId: z.string().optional().or(z.literal("")),
  startDate: z.string().min(1, "Start date is required."),
  endDate: z.string().optional().or(z.literal("")),
});
export type VAPTEngagementFormValues = z.infer<typeof vaptEngagementFormSchema>;

export const vaptFindingFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  severity: z.enum(findingSeverityValues),
  cvssScore: z.coerce.number().min(0).max(10).optional(),
  description: z.string().min(2, "Description is required."),
  recommendation: z.string().min(2, "Recommendation is required."),
  reportedDate: z.string().min(1, "Reported date is required."),
});
export type VAPTFindingFormValues = z.infer<typeof vaptFindingFormSchema>;
