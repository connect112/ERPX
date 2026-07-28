import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type QuotationCreatePayload,
  type QuotationListParams,
  type QuotationUpdatePayload,
  quotationsApi,
} from "@/features/corporate/quotations/api/quotations-api";

const quotationsKeys = {
  all: ["corporate", "quotations"] as const,
  list: (params: QuotationListParams) => [...quotationsKeys.all, "list", params] as const,
  detail: (id: string) => [...quotationsKeys.all, "detail", id] as const,
};

export function useQuotationsList(params: QuotationListParams) {
  return useQuery({
    queryKey: quotationsKeys.list(params),
    queryFn: () => quotationsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useQuotation(id: string | undefined) {
  return useQuery({
    queryKey: quotationsKeys.detail(id ?? ""),
    queryFn: () => quotationsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateQuotation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: QuotationCreatePayload) => quotationsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quotationsKeys.all }),
  });
}

export function useUpdateQuotation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: QuotationUpdatePayload) => quotationsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quotationsKeys.all }),
  });
}

export function useSendQuotation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => quotationsApi.send(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quotationsKeys.all }),
  });
}

export function useAcceptQuotation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => quotationsApi.accept(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quotationsKeys.all }),
  });
}

export function useRejectQuotation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rejectionReason?: string) => quotationsApi.reject(id, rejectionReason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quotationsKeys.all }),
  });
}
