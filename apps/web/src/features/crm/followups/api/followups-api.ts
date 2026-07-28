import { apiClient } from "@/api/client";
import type { FollowUpStatus, FollowUpType } from "@/features/crm/followups/schemas/followup-schemas";

export interface FollowUpPublic {
  id: string;
  lead_id: string;
  created_by_user_id: string | null;
  follow_up_type: FollowUpType;
  status: FollowUpStatus;
  scheduled_at: string;
  completed_at: string | null;
  outcome: string | null;
  notes: string | null;
  created_at: string;
}

export interface FollowUpCreatePayload {
  follow_up_type: FollowUpType;
  scheduled_at: string;
  notes?: string;
}

export interface FollowUpUpdatePayload {
  follow_up_type?: FollowUpType;
  scheduled_at?: string;
  status?: FollowUpStatus;
  notes?: string;
}

export interface FollowUpCompletePayload {
  outcome: string;
  notes?: string;
}

export const followupsApi = {
  list: (leadId: string) =>
    apiClient.get<FollowUpPublic[]>(`/crm/leads/${leadId}/followups`).then((r) => r.data),

  create: (leadId: string, payload: FollowUpCreatePayload) =>
    apiClient.post<FollowUpPublic>(`/crm/leads/${leadId}/followups`, payload).then((r) => r.data),

  update: (leadId: string, followupId: string, payload: FollowUpUpdatePayload) =>
    apiClient
      .patch<FollowUpPublic>(`/crm/leads/${leadId}/followups/${followupId}`, payload)
      .then((r) => r.data),

  complete: (leadId: string, followupId: string, payload: FollowUpCompletePayload) =>
    apiClient
      .post<FollowUpPublic>(`/crm/leads/${leadId}/followups/${followupId}/complete`, payload)
      .then((r) => r.data),

  remove: (leadId: string, followupId: string) =>
    apiClient.delete(`/crm/leads/${leadId}/followups/${followupId}`).then((r) => r.data),
};
