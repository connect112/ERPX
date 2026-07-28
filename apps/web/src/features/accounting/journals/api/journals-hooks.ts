import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type JournalEntryCreatePayload,
  type JournalListParams,
  journalsApi,
} from "@/features/accounting/journals/api/journals-api";

const journalsKeys = {
  all: ["accounting", "journals"] as const,
  list: (params: JournalListParams) => [...journalsKeys.all, "list", params] as const,
  detail: (id: string) => [...journalsKeys.all, "detail", id] as const,
};

export function useJournalsList(params: JournalListParams) {
  return useQuery({
    queryKey: journalsKeys.list(params),
    queryFn: () => journalsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useJournalEntry(id: string | undefined) {
  return useQuery({
    queryKey: journalsKeys.detail(id ?? ""),
    queryFn: () => journalsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateJournalEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: JournalEntryCreatePayload) => journalsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: journalsKeys.all }),
  });
}

export function usePostJournalEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => journalsApi.post(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: journalsKeys.all }),
  });
}

export function useReverseJournalEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => journalsApi.reverse(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: journalsKeys.all }),
  });
}
