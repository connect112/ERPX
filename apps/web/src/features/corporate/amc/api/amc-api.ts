import { apiClient } from "@/api/client";
import type {
  AMCStatus,
  AMCVisitStatus,
  BillingFrequency,
} from "@/features/corporate/amc/schemas/amc-schemas";

export interface AMCContractPublic {
  id: string;
  organization_id: string;
  client_id: string;
  contract_id: string | null;
  amc_number: string;
  coverage_description: string;
  start_date: string;
  end_date: string;
  renewal_reminder_days: number;
  amount: number;
  billing_frequency: BillingFrequency;
  status: AMCStatus;
  created_at: string;
}

export interface AMCContractListResponse {
  items: AMCContractPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface AMCContractListParams {
  client_id?: string;
  status?: AMCStatus;
  skip?: number;
  limit?: number;
}

export interface AMCContractCreatePayload {
  client_id: string;
  contract_id?: string;
  amc_number: string;
  coverage_description: string;
  start_date: string;
  end_date: string;
  renewal_reminder_days?: number;
  amount: number;
  billing_frequency: BillingFrequency;
}

export interface AMCContractUpdatePayload {
  coverage_description?: string;
  end_date?: string;
  renewal_reminder_days?: number;
  amount?: number;
  billing_frequency?: BillingFrequency;
  status?: AMCStatus;
}

export interface AMCVisitPublic {
  id: string;
  amc_contract_id: string;
  engineer_employee_id: string | null;
  visit_date: string;
  purpose: string;
  findings: string | null;
  status: AMCVisitStatus;
  created_at: string;
}

export interface AMCVisitCreatePayload {
  visit_date: string;
  purpose: string;
  engineer_employee_id?: string;
}

export const amcApi = {
  list: (params: AMCContractListParams) =>
    apiClient.get<AMCContractListResponse>("/corporate/amc/contracts", { params }).then((r) => r.data),

  listDueForRenewal: () =>
    apiClient.get<AMCContractPublic[]>("/corporate/amc/contracts/due-for-renewal").then((r) => r.data),

  create: (payload: AMCContractCreatePayload) =>
    apiClient.post<AMCContractPublic>("/corporate/amc/contracts", payload).then((r) => r.data),

  update: (id: string, payload: AMCContractUpdatePayload) =>
    apiClient.patch<AMCContractPublic>(`/corporate/amc/contracts/${id}`, payload).then((r) => r.data),

  createVisit: (contractId: string, payload: AMCVisitCreatePayload) =>
    apiClient
      .post<AMCVisitPublic>(`/corporate/amc/contracts/${contractId}/visits`, payload)
      .then((r) => r.data),

  listVisits: (contractId: string, status?: AMCVisitStatus) =>
    apiClient
      .get<AMCVisitPublic[]>(`/corporate/amc/contracts/${contractId}/visits`, { params: { status } })
      .then((r) => r.data),

  completeVisit: (visitId: string, findings: string) =>
    apiClient
      .post<AMCVisitPublic>(`/corporate/amc/visits/${visitId}/complete`, { findings })
      .then((r) => r.data),

  cancelVisit: (visitId: string) =>
    apiClient.post<AMCVisitPublic>(`/corporate/amc/visits/${visitId}/cancel`).then((r) => r.data),
};
