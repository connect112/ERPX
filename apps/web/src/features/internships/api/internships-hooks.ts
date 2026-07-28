import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type InternshipPostingCreatePayload,
  type InternshipPostingListParams,
  type InternshipPostingUpdatePayload,
  internshipsApi,
} from "@/features/internships/api/internships-api";
import type {
  InternshipApplicationStatus,
  InternshipPostingStatus,
  InternshipStatus,
} from "@/features/internships/schemas/posting-schemas";
import { useCompaniesList } from "@/features/placements/api/placements-hooks";

const internshipsKeys = {
  all: ["internships"] as const,
  postings: (params: InternshipPostingListParams) => [...internshipsKeys.all, "postings", params] as const,
  posting: (id: string) => [...internshipsKeys.all, "postings", id] as const,
  applications: (id: string) => [...internshipsKeys.all, "postings", id, "applications"] as const,
  internships: (params: { skip?: number; limit?: number }) =>
    [...internshipsKeys.all, "internships", params] as const,
};

export { useCompaniesList };

export function usePostingsList(params: InternshipPostingListParams) {
  return useQuery({
    queryKey: internshipsKeys.postings(params),
    queryFn: () => internshipsApi.listPostings(params),
    placeholderData: keepPreviousData,
  });
}

export function usePosting(id: string | undefined) {
  return useQuery({
    queryKey: internshipsKeys.posting(id ?? ""),
    queryFn: () => internshipsApi.getPosting(id as string),
    enabled: !!id,
  });
}

export function usePostingApplications(id: string | undefined) {
  return useQuery({
    queryKey: internshipsKeys.applications(id ?? ""),
    queryFn: () => internshipsApi.listPostingApplications(id as string),
    enabled: !!id,
  });
}

export function useCreatePosting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InternshipPostingCreatePayload) => internshipsApi.createPosting(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: internshipsKeys.all }),
  });
}

export function useUpdatePosting(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InternshipPostingUpdatePayload) => internshipsApi.updatePosting(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: internshipsKeys.all }),
  });
}

export function useChangePostingStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (status: InternshipPostingStatus) => internshipsApi.changePostingStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: internshipsKeys.all }),
  });
}

export function useChangeApplicationStatus(postingId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      applicationId,
      status,
      notes,
    }: {
      applicationId: string;
      status: InternshipApplicationStatus;
      notes?: string;
    }) => internshipsApi.changeApplicationStatus(applicationId, status, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: internshipsKeys.applications(postingId) });
      queryClient.invalidateQueries({ queryKey: internshipsKeys.all });
    },
  });
}

export function useInternshipsList(params: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: internshipsKeys.internships(params),
    queryFn: () => internshipsApi.listInternships(params),
    placeholderData: keepPreviousData,
  });
}

export function useUpdateInternship() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: { mentor_employee_id?: string; end_date?: string; stipend?: number; feedback?: string };
    }) => internshipsApi.updateInternship(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: internshipsKeys.all }),
  });
}

export function useChangeInternshipStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: InternshipStatus }) =>
      internshipsApi.changeInternshipStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: internshipsKeys.all }),
  });
}
