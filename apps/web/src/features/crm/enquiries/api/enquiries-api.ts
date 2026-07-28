import { apiClient } from "@/api/client";
import type { EnquiryStatus } from "@/features/crm/enquiries/schemas/enquiry-schemas";

export interface EnquiryPublic {
  id: string;
  lead_id: string;
  course_interest: string;
  budget: number | null;
  preferred_batch_timing: string | null;
  status: EnquiryStatus;
  notes: string | null;
  created_at: string;
}

export interface EnquiryCreatePayload {
  course_interest: string;
  budget?: number;
  preferred_batch_timing?: string;
  notes?: string;
}

export interface EnquiryUpdatePayload {
  course_interest?: string;
  budget?: number;
  preferred_batch_timing?: string;
  status?: EnquiryStatus;
  notes?: string;
}

export const enquiriesApi = {
  list: (leadId: string) =>
    apiClient.get<EnquiryPublic[]>(`/crm/leads/${leadId}/enquiries`).then((r) => r.data),

  create: (leadId: string, payload: EnquiryCreatePayload) =>
    apiClient.post<EnquiryPublic>(`/crm/leads/${leadId}/enquiries`, payload).then((r) => r.data),

  update: (leadId: string, enquiryId: string, payload: EnquiryUpdatePayload) =>
    apiClient
      .patch<EnquiryPublic>(`/crm/leads/${leadId}/enquiries/${enquiryId}`, payload)
      .then((r) => r.data),

  remove: (leadId: string, enquiryId: string) =>
    apiClient.delete(`/crm/leads/${leadId}/enquiries/${enquiryId}`).then((r) => r.data),
};
