import { apiClient } from "@/api/client";

export interface ClientPublic {
  id: string;
  organization_id: string;
  branch_id: string | null;
  accounting_customer_id: string | null;
  account_manager_user_id: string | null;
  client_code: string;
  name: string;
  industry: string | null;
  website: string | null;
  gstin: string | null;
  contact_person_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  postal_code: string | null;
  status: "prospect" | "active" | "inactive" | "churned";
  notes: string | null;
  created_at: string;
}

export const clientApi = {
  me: () => apiClient.get<ClientPublic>("/corporate/clients/me").then((r) => r.data),
};
