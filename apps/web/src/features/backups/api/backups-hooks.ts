import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { backupsApi } from "@/features/backups/api/backups-api";

const backupsKeys = {
  all: ["backups"] as const,
  list: (params: { skip?: number; limit?: number }) => [...backupsKeys.all, "list", params] as const,
};

export function useBackupsList(params: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: backupsKeys.list(params),
    queryFn: () => backupsApi.list(params),
    refetchInterval: (query) =>
      query.state.data?.items.some((j) => j.status === "running" || j.status === "pending") ? 2000 : false,
  });
}

export function useTriggerBackup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => backupsApi.trigger(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: backupsKeys.all }),
  });
}

export function useBackupDownloadUrl() {
  return useMutation({
    mutationFn: (id: string) => backupsApi.getDownloadUrl(id),
  });
}
