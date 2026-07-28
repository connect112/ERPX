import { apiClient } from "@/api/client";
import type {
  FindingSeverity,
  FindingStatus,
  VAPTEngagementStatus,
  VAPTEngagementType,
} from "@/features/corporate/vapt/schemas/vapt-schemas";

export interface VAPTEngagementPublic {
  id: string;
  organization_id: string;
  project_id: string;
  lead_tester_employee_id: string | null;
  scope_description: string;
  engagement_type: VAPTEngagementType;
  methodology: string | null;
  status: VAPTEngagementStatus;
  start_date: string;
  end_date: string | null;
  created_at: string;
}

export interface VAPTEngagementCreatePayload {
  project_id: string;
  scope_description: string;
  engagement_type: VAPTEngagementType;
  methodology?: string;
  lead_tester_employee_id?: string;
  start_date: string;
  end_date?: string;
}

export interface VAPTEngagementUpdatePayload {
  scope_description?: string;
  methodology?: string;
  lead_tester_employee_id?: string;
  status?: VAPTEngagementStatus;
  start_date?: string;
  end_date?: string;
}

export interface VAPTFindingPublic {
  id: string;
  engagement_id: string;
  title: string;
  severity: FindingSeverity;
  cvss_score: number | null;
  description: string;
  recommendation: string;
  status: FindingStatus;
  reported_date: string;
  closed_date: string | null;
  created_at: string;
}

export interface VAPTFindingCreatePayload {
  title: string;
  severity: FindingSeverity;
  cvss_score?: number;
  description: string;
  recommendation: string;
  reported_date: string;
}

export interface VAPTFindingUpdatePayload {
  title?: string;
  severity?: FindingSeverity;
  cvss_score?: number;
  description?: string;
  recommendation?: string;
  status?: FindingStatus;
  closed_date?: string;
}

export interface VAPTFindingsSummary {
  engagement_id: string;
  total_findings: number;
  open_findings: number;
  by_severity: Record<string, number>;
}

export const vaptApi = {
  listByProject: (projectId: string) =>
    apiClient
      .get<VAPTEngagementPublic[]>(`/corporate/vapt/engagements/projects/${projectId}`)
      .then((r) => r.data),

  create: (payload: VAPTEngagementCreatePayload) =>
    apiClient.post<VAPTEngagementPublic>("/corporate/vapt/engagements", payload).then((r) => r.data),

  update: (id: string, payload: VAPTEngagementUpdatePayload) =>
    apiClient.patch<VAPTEngagementPublic>(`/corporate/vapt/engagements/${id}`, payload).then((r) => r.data),

  summary: (id: string) =>
    apiClient.get<VAPTFindingsSummary>(`/corporate/vapt/engagements/${id}/summary`).then((r) => r.data),

  createFinding: (engagementId: string, payload: VAPTFindingCreatePayload) =>
    apiClient
      .post<VAPTFindingPublic>(`/corporate/vapt/engagements/${engagementId}/findings`, payload)
      .then((r) => r.data),

  listFindings: (engagementId: string, status?: FindingStatus) =>
    apiClient
      .get<VAPTFindingPublic[]>(`/corporate/vapt/engagements/${engagementId}/findings`, { params: { status } })
      .then((r) => r.data),

  updateFinding: (findingId: string, payload: VAPTFindingUpdatePayload) =>
    apiClient.patch<VAPTFindingPublic>(`/corporate/vapt/findings/${findingId}`, payload).then((r) => r.data),
};
