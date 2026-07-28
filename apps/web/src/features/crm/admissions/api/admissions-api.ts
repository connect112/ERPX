import { apiClient } from "@/api/client";
import type { AdmissionStatus } from "@/features/crm/admissions/schemas/admission-schemas";

export interface AdmissionPublic {
  id: string;
  lead_id: string;
  organization_id: string;
  branch_id: string | null;
  course_name: string;
  batch_name: string | null;
  fee_amount: number;
  discount_amount: number;
  admission_date: string;
  status: AdmissionStatus;
  created_at: string;
}

export interface AdmissionCreatePayload {
  branch_id?: string;
  course_name: string;
  batch_name?: string;
  fee_amount: number;
  discount_amount?: number;
  admission_date: string;
}

export interface AdmissionUpdatePayload {
  branch_id?: string;
  course_name?: string;
  batch_name?: string;
  fee_amount?: number;
  discount_amount?: number;
  admission_date?: string;
  status?: AdmissionStatus;
}

export const admissionsApi = {
  listAll: () => apiClient.get<AdmissionPublic[]>("/crm/admissions").then((r) => r.data),

  getForLead: (leadId: string) =>
    apiClient.get<AdmissionPublic>(`/crm/leads/${leadId}/admission`).then((r) => r.data),

  create: (leadId: string, payload: AdmissionCreatePayload) =>
    apiClient.post<AdmissionPublic>(`/crm/leads/${leadId}/admission`, payload).then((r) => r.data),

  update: (admissionId: string, payload: AdmissionUpdatePayload) =>
    apiClient.patch<AdmissionPublic>(`/crm/admissions/${admissionId}`, payload).then((r) => r.data),

  cancel: (admissionId: string) =>
    apiClient.post<AdmissionPublic>(`/crm/admissions/${admissionId}/cancel`).then((r) => r.data),
};
