import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ReferralCreatePayload,
  type ReferralListParams,
  type ReferralProgramCreatePayload,
  type ReferralProgramUpdatePayload,
  referralsApi,
} from "@/features/marketing/referrals/api/referrals-api";

const referralProgramsKey = ["marketing", "referral-programs"] as const;
const referralsKeys = {
  all: ["marketing", "referrals"] as const,
  list: (params: ReferralListParams) => [...referralsKeys.all, "list", params] as const,
};

export function useReferralPrograms(isActive?: boolean) {
  return useQuery({
    queryKey: [...referralProgramsKey, isActive],
    queryFn: () => referralsApi.listPrograms(isActive),
  });
}

export function useCreateReferralProgram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReferralProgramCreatePayload) => referralsApi.createProgram(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: referralProgramsKey }),
  });
}

export function useUpdateReferralProgram() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ReferralProgramUpdatePayload }) =>
      referralsApi.updateProgram(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: referralProgramsKey }),
  });
}

export function useReferralsList(params: ReferralListParams) {
  return useQuery({
    queryKey: referralsKeys.list(params),
    queryFn: () => referralsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCreateReferral() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReferralCreatePayload) => referralsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: referralsKeys.all }),
  });
}

export function useConvertReferral() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, convertedLeadId }: { id: string; convertedLeadId: string }) =>
      referralsApi.convert(id, convertedLeadId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: referralsKeys.all }),
  });
}

export function useRewardReferral() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => referralsApi.reward(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: referralsKeys.all }),
  });
}

export function useRejectReferral() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => referralsApi.reject(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: referralsKeys.all }),
  });
}
