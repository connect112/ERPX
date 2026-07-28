import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type CouponCreatePayload,
  type CouponListParams,
  type CouponUpdatePayload,
  couponsApi,
} from "@/features/marketing/coupons/api/coupons-api";

const couponsKeys = {
  all: ["marketing", "coupons"] as const,
  list: (params: CouponListParams) => [...couponsKeys.all, "list", params] as const,
  detail: (id: string) => [...couponsKeys.all, "detail", id] as const,
  usageSummary: (id: string) => [...couponsKeys.all, id, "usage-summary"] as const,
  redemptions: (id: string, params: { skip?: number; limit?: number }) =>
    [...couponsKeys.all, id, "redemptions", params] as const,
};

export function useCouponsList(params: CouponListParams) {
  return useQuery({
    queryKey: couponsKeys.list(params),
    queryFn: () => couponsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCoupon(id: string | undefined) {
  return useQuery({
    queryKey: couponsKeys.detail(id ?? ""),
    queryFn: () => couponsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCouponUsageSummary(id: string | undefined) {
  return useQuery({
    queryKey: couponsKeys.usageSummary(id ?? ""),
    queryFn: () => couponsApi.usageSummary(id as string),
    enabled: !!id,
  });
}

export function useCouponRedemptions(id: string | undefined, params: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: couponsKeys.redemptions(id ?? "", params),
    queryFn: () => couponsApi.listRedemptions(id as string, params),
    enabled: !!id,
    placeholderData: keepPreviousData,
  });
}

export function useCreateCoupon() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CouponCreatePayload) => couponsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: couponsKeys.all }),
  });
}

export function useUpdateCoupon(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CouponUpdatePayload) => couponsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: couponsKeys.all }),
  });
}
