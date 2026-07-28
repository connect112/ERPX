import { apiClient } from "@/api/client";
import type { ContractStatus, ContractType } from "@/features/corporate/contracts/schemas/contract-schemas";

export interface ContractPublic {
  id: string;
  organization_id: string;
  client_id: string;
  project_id: string | null;
  quotation_id: string | null;
  contract_number: string;
  contract_type: ContractType;
  start_date: string;
  end_date: string | null;
  contract_value: number;
  status: ContractStatus;
  signed_date: string | null;
  document_url: string | null;
  notes: string | null;
  created_at: string;
}

export interface ContractListResponse {
  items: ContractPublic[];
  total: number;
  skip: number;
  limit: number;
}

export interface ContractListParams {
  client_id?: string;
  status?: ContractStatus;
  skip?: number;
  limit?: number;
}

export interface ContractCreatePayload {
  client_id: string;
  project_id?: string;
  quotation_id?: string;
  contract_number: string;
  contract_type: ContractType;
  start_date: string;
  end_date?: string;
  contract_value: number;
  document_url?: string;
  notes?: string;
}

export interface ContractUpdatePayload {
  end_date?: string;
  contract_value?: number;
  document_url?: string;
  notes?: string;
}

export const contractsApi = {
  list: (params: ContractListParams) =>
    apiClient.get<ContractListResponse>("/corporate/contracts", { params }).then((r) => r.data),

  listExpiring: (withinDays?: number) =>
    apiClient
      .get<ContractPublic[]>("/corporate/contracts/expiring", { params: { within_days: withinDays } })
      .then((r) => r.data),

  create: (payload: ContractCreatePayload) =>
    apiClient.post<ContractPublic>("/corporate/contracts", payload).then((r) => r.data),

  update: (id: string, payload: ContractUpdatePayload) =>
    apiClient.patch<ContractPublic>(`/corporate/contracts/${id}`, payload).then((r) => r.data),

  activate: (id: string, signedDate: string) =>
    apiClient
      .post<ContractPublic>(`/corporate/contracts/${id}/activate`, { signed_date: signedDate })
      .then((r) => r.data),

  terminate: (id: string) =>
    apiClient.post<ContractPublic>(`/corporate/contracts/${id}/terminate`).then((r) => r.data),

  renew: (id: string, newEndDate: string, newContractValue?: number) =>
    apiClient
      .post<ContractPublic>(`/corporate/contracts/${id}/renew`, {
        new_end_date: newEndDate,
        new_contract_value: newContractValue,
      })
      .then((r) => r.data),

  markExpired: (id: string) =>
    apiClient.post<ContractPublic>(`/corporate/contracts/${id}/mark-expired`).then((r) => r.data),
};
