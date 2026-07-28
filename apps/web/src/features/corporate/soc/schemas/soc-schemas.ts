import { z } from "zod";

export const socServiceTypeValues = [
  "monitoring",
  "incident_response",
  "threat_hunting",
  "log_management",
] as const;
export type SOCServiceType = (typeof socServiceTypeValues)[number];

export const socServiceTypeLabels: Record<SOCServiceType, string> = {
  monitoring: "Monitoring",
  incident_response: "Incident Response",
  threat_hunting: "Threat Hunting",
  log_management: "Log Management",
};

export const socServiceStatusValues = ["active", "suspended", "terminated"] as const;
export type SOCServiceStatus = (typeof socServiceStatusValues)[number];

export const socServiceStatusLabels: Record<SOCServiceStatus, string> = {
  active: "Active",
  suspended: "Suspended",
  terminated: "Terminated",
};

export const incidentSeverityValues = ["critical", "high", "medium", "low"] as const;
export type IncidentSeverity = (typeof incidentSeverityValues)[number];

export const incidentSeverityLabels: Record<IncidentSeverity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const incidentStatusValues = ["open", "investigating", "contained", "resolved", "closed"] as const;
export type IncidentStatus = (typeof incidentStatusValues)[number];

export const incidentStatusLabels: Record<IncidentStatus, string> = {
  open: "Open",
  investigating: "Investigating",
  contained: "Contained",
  resolved: "Resolved",
  closed: "Closed",
};

export const socServiceFormSchema = z.object({
  projectId: z.string().optional().or(z.literal("")),
  serviceType: z.enum(socServiceTypeValues),
  slaResponseTimeMinutes: z.coerce.number().min(1).optional(),
  startDate: z.string().min(1, "Start date is required."),
  endDate: z.string().optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type SOCServiceFormValues = z.infer<typeof socServiceFormSchema>;

export const socIncidentFormSchema = z.object({
  title: z.string().min(2, "Title is required."),
  severity: z.enum(incidentSeverityValues),
  description: z.string().min(2, "Description is required."),
  detectedAt: z.string().min(1, "Detected-at is required."),
  assignedToEmployeeId: z.string().optional().or(z.literal("")),
});
export type SOCIncidentFormValues = z.infer<typeof socIncidentFormSchema>;
