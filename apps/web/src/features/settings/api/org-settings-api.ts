import { apiClient } from "@/api/client";

export interface OrgSettingPublic {
  id: string;
  organization_id: string;
  key: string;
  value: string;
  updated_at: string;
}

export interface OrgSettingUpsertPayload {
  key: string;
  value: string;
}

export const orgSettingsApi = {
  list: (organizationId: string) =>
    apiClient.get<OrgSettingPublic[]>(`/settings/${organizationId}`).then((r) => r.data),

  upsert: (organizationId: string, payload: OrgSettingUpsertPayload) =>
    apiClient.put<OrgSettingPublic>(`/settings/${organizationId}`, payload).then((r) => r.data),
};
