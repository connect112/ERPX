import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { placementsApi } from "@/features/placements/api/placements-api";

export function useExternalJobs(params: { q?: string; experience?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ["placements", "external", params],
    queryFn: () => placementsApi.externalJobs(params),
    placeholderData: keepPreviousData,
  });
}

export function useBrowseJobPostings() {
  return useQuery({
    queryKey: ["placements", "postings", "browse"],
    queryFn: () => placementsApi.browsePostings(),
  });
}

export function useMyPlacementApplications() {
  return useQuery({
    queryKey: ["placements", "applications", "me"],
    queryFn: () => placementsApi.myApplications(),
  });
}

export function useApplyToJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ postingId, coverLetter }: { postingId: string; coverLetter?: string }) =>
      placementsApi.apply(postingId, coverLetter),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["placements", "applications", "me"] });
    },
  });
}

export function useWithdrawPlacementApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) => placementsApi.withdraw(applicationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["placements", "applications", "me"] });
    },
  });
}
