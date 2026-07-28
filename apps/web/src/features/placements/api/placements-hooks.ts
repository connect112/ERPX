import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type CompanyPayload,
  type JobPostingCreatePayload,
  type JobPostingListParams,
  type JobPostingUpdatePayload,
  placementsApi,
} from "@/features/placements/api/placements-api";
import type {
  ApplicationStatus,
  PostingStatus,
} from "@/features/placements/schemas/posting-schemas";

const placementsKeys = {
  all: ["placements"] as const,
  companies: (params: { skip?: number; limit?: number }) =>
    [...placementsKeys.all, "companies", params] as const,
  postings: (params: JobPostingListParams) => [...placementsKeys.all, "postings", params] as const,
  posting: (id: string) => [...placementsKeys.all, "postings", id] as const,
  applications: (id: string) => [...placementsKeys.all, "postings", id, "applications"] as const,
};

export function useCompaniesList(params: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: placementsKeys.companies(params),
    queryFn: () => placementsApi.listCompanies(params),
    placeholderData: keepPreviousData,
  });
}

export function useCreateCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CompanyPayload) => placementsApi.createCompany(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: placementsKeys.all }),
  });
}

export function useUpdateCompany(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<CompanyPayload>) => placementsApi.updateCompany(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: placementsKeys.all }),
  });
}

export function useDeleteCompany() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => placementsApi.deleteCompany(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: placementsKeys.all }),
  });
}

export function usePostingsList(params: JobPostingListParams) {
  return useQuery({
    queryKey: placementsKeys.postings(params),
    queryFn: () => placementsApi.listPostings(params),
    placeholderData: keepPreviousData,
  });
}

export function usePosting(id: string | undefined) {
  return useQuery({
    queryKey: placementsKeys.posting(id ?? ""),
    queryFn: () => placementsApi.getPosting(id as string),
    enabled: !!id,
  });
}

export function usePostingApplications(id: string | undefined) {
  return useQuery({
    queryKey: placementsKeys.applications(id ?? ""),
    queryFn: () => placementsApi.listPostingApplications(id as string),
    enabled: !!id,
  });
}

export function useCreatePosting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: JobPostingCreatePayload) => placementsApi.createPosting(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: placementsKeys.all }),
  });
}

export function useUpdatePosting(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: JobPostingUpdatePayload) => placementsApi.updatePosting(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: placementsKeys.all }),
  });
}

export function useChangePostingStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (status: PostingStatus) => placementsApi.changePostingStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: placementsKeys.all }),
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
      status: ApplicationStatus;
      notes?: string;
    }) => placementsApi.changeApplicationStatus(applicationId, status, notes),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: placementsKeys.applications(postingId) }),
  });
}
