import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type OrgSettingUpsertPayload, orgSettingsApi } from "@/features/settings/api/org-settings-api";

const orgSettingsKey = (organizationId: string) => ["settings", organizationId] as const;

export function useOrgSettings(organizationId: string | undefined) {
  return useQuery({
    queryKey: orgSettingsKey(organizationId ?? ""),
    queryFn: () => orgSettingsApi.list(organizationId as string),
    enabled: !!organizationId,
  });
}

export function useUpsertOrgSetting(organizationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OrgSettingUpsertPayload) => orgSettingsApi.upsert(organizationId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orgSettingsKey(organizationId) }),
  });
}
