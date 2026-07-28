import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AxiosError } from "axios";

import {
  type AdmissionCreatePayload,
  type AdmissionUpdatePayload,
  admissionsApi,
} from "@/features/crm/admissions/api/admissions-api";

const admissionsAllKey = ["crm", "admissions", "all"] as const;
const admissionForLeadKey = (leadId: string) => ["crm", "leads", leadId, "admission"] as const;

export function useAdmissions() {
  return useQuery({
    queryKey: admissionsAllKey,
    queryFn: admissionsApi.listAll,
  });
}

export function useAdmissionForLead(leadId: string) {
  return useQuery({
    queryKey: admissionForLeadKey(leadId),
    queryFn: () => admissionsApi.getForLead(leadId),
    enabled: !!leadId,
    retry: (failureCount, error) => {
      const status = (error as AxiosError).response?.status;
      if (status === 404) return false;
      return failureCount < 1;
    },
  });
}

export function useCreateAdmission(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdmissionCreatePayload) => admissionsApi.create(leadId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: admissionForLeadKey(leadId) });
      queryClient.invalidateQueries({ queryKey: admissionsAllKey });
      queryClient.invalidateQueries({ queryKey: ["crm", "leads", "detail", leadId] });
    },
  });
}

export function useUpdateAdmission(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      admissionId,
      payload,
    }: {
      admissionId: string;
      payload: AdmissionUpdatePayload;
    }) => admissionsApi.update(admissionId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: admissionForLeadKey(leadId) });
      queryClient.invalidateQueries({ queryKey: admissionsAllKey });
    },
  });
}

export function useCancelAdmission(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (admissionId: string) => admissionsApi.cancel(admissionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: admissionForLeadKey(leadId) });
      queryClient.invalidateQueries({ queryKey: admissionsAllKey });
    },
  });
}
