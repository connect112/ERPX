import { apiClient } from "@/api/client";

export interface ContractPublic {
  id: string;
  organization_id: string;
  client_id: string;
  project_id: string | null;
  quotation_id: string | null;
  contract_number: string;
  contract_type: "project" | "amc" | "retainer" | "soc_subscription" | "other";
  start_date: string;
  end_date: string | null;
  contract_value: number;
  status: "draft" | "active" | "expired" | "terminated" | "renewed";
  signed_date: string | null;
  document_url: string | null;
  notes: string | null;
  created_at: string;
}

export const contractsApi = {
  myContracts: () => apiClient.get<ContractPublic[]>("/corporate/contracts/me").then((r) => r.data),
};
