import { apiClient } from "@/api/client";

export type IntegrationTestStatus = "success" | "failed";

export interface IntegrationPublic {
  id: string;
  organization_id: string;
  created_by_user_id: string | null;
  provider: string;
  name: string;
  base_url: string;
  masked_api_key: string | null;
  config: string | null;
  is_enabled: boolean;
  last_tested_at: string | null;
  last_test_status: IntegrationTestStatus | null;
  last_test_message: string | null;
  created_at: string;
}

export interface IntegrationListResponse {
  items: IntegrationPublic[];
  total: number;
}

export interface IntegrationCreatePayload {
  provider: string;
  name: string;
  base_url: string;
  api_key?: string;
  is_enabled: boolean;
}

export type IntegrationUpdatePayload = Partial<IntegrationCreatePayload>;

export const integrationsApi = {
  list: (params: { skip?: number; limit?: number }) =>
    apiClient.get<IntegrationListResponse>("/integrations", { params }).then((r) => r.data),

  create: (payload: IntegrationCreatePayload) =>
    apiClient.post<IntegrationPublic>("/integrations", payload).then((r) => r.data),

  update: (id: string, payload: IntegrationUpdatePayload) =>
    apiClient.patch<IntegrationPublic>(`/integrations/${id}`, payload).then((r) => r.data),

  remove: (id: string) => apiClient.delete(`/integrations/${id}`).then((r) => r.data),

  test: (id: string) => apiClient.post<IntegrationPublic>(`/integrations/${id}/test`).then((r) => r.data),
};
