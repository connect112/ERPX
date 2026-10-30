import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type FileFilters, storageApi } from "@/features/storage-manager/api/storage-api";

const keys = {
  all: ["storage-manager"] as const,
  files: (filters: FileFilters) => [...keys.all, "files", filters] as const,
  usage: () => [...keys.all, "usage"] as const,
  duplicates: () => [...keys.all, "duplicates"] as const,
  server: () => [...keys.all, "server"] as const,
  analysis: (id: string) => [...keys.all, "analysis", id] as const,
  trash: (closed: boolean) => [...keys.all, "trash", closed] as const,
  log: (skip: number, limit: number) => [...keys.all, "log", skip, limit] as const,
};

export function useFiles(filters: FileFilters) {
  return useQuery({ queryKey: keys.files(filters), queryFn: () => storageApi.files(filters), placeholderData: keepPreviousData });
}

export const useUsage = () => useQuery({ queryKey: keys.usage(), queryFn: storageApi.usage });
export const useDuplicates = (enabled: boolean) =>
  useQuery({ queryKey: keys.duplicates(), queryFn: storageApi.duplicates, enabled });
export const useServerStatus = (enabled: boolean) =>
  useQuery({ queryKey: keys.server(), queryFn: storageApi.server, enabled, retry: false });
export const useAnalysis = (id: string | null) =>
  useQuery({ queryKey: keys.analysis(id ?? ""), queryFn: () => storageApi.analysis(id as string), enabled: id !== null });
export const useTrash = (includeClosed = false) =>
  useQuery({ queryKey: keys.trash(includeClosed), queryFn: () => storageApi.trash(includeClosed) });
export const useDeletionLog = (skip: number, limit: number) =>
  useQuery({ queryKey: keys.log(skip, limit), queryFn: () => storageApi.log(skip, limit), placeholderData: keepPreviousData });

export function useDeletionPreview() {
  return useMutation({ mutationFn: (ids: string[]) => storageApi.previewDeletion(ids) });
}

// Anything that changes storage refreshes every list, usage figure and the log.
function useInvalidateAll() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: keys.all });
}

export function useDeleteFiles() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: storageApi.deleteFiles, onSuccess: invalidate });
}

export function useRestore() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: string) => storageApi.restore(id), onSuccess: invalidate });
}

export function usePurge() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: storageApi.purge, onSuccess: invalidate });
}

export function errorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: { error?: { message?: string }; detail?: unknown } } })?.response?.data;
  if (data?.error?.message) return data.error.message;
  if (typeof data?.detail === "string") return data.detail;
  return fallback;
}
