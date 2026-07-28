import { apiClient } from "@/api/client";
import type {
  CounsellingMode,
  CounsellingStatus,
} from "@/features/crm/counselling/schemas/counselling-schemas";

export interface CounsellingSessionPublic {
  id: string;
  lead_id: string;
  counselor_user_id: string | null;
  mode: CounsellingMode;
  status: CounsellingStatus;
  scheduled_at: string;
  recommended_course: string | null;
  notes: string | null;
  created_at: string;
}

export interface CounsellingCreatePayload {
  counselor_user_id?: string;
  mode: CounsellingMode;
  scheduled_at: string;
  notes?: string;
}

export interface CounsellingUpdatePayload {
  counselor_user_id?: string;
  mode?: CounsellingMode;
  status?: CounsellingStatus;
  scheduled_at?: string;
  recommended_course?: string;
  notes?: string;
}

export interface CounsellingCompletePayload {
  recommended_course?: string;
  notes?: string;
}

export const counsellingApi = {
  list: (leadId: string) =>
    apiClient.get<CounsellingSessionPublic[]>(`/crm/leads/${leadId}/counselling`).then((r) => r.data),

  create: (leadId: string, payload: CounsellingCreatePayload) =>
    apiClient
      .post<CounsellingSessionPublic>(`/crm/leads/${leadId}/counselling`, payload)
      .then((r) => r.data),

  update: (leadId: string, sessionId: string, payload: CounsellingUpdatePayload) =>
    apiClient
      .patch<CounsellingSessionPublic>(`/crm/leads/${leadId}/counselling/${sessionId}`, payload)
      .then((r) => r.data),

  complete: (leadId: string, sessionId: string, payload: CounsellingCompletePayload) =>
    apiClient
      .post<CounsellingSessionPublic>(`/crm/leads/${leadId}/counselling/${sessionId}/complete`, payload)
      .then((r) => r.data),

  remove: (leadId: string, sessionId: string) =>
    apiClient.delete(`/crm/leads/${leadId}/counselling/${sessionId}`).then((r) => r.data),
};
