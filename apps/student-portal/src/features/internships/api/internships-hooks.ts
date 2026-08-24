import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { internshipsApi } from "@/features/internships/api/internships-api";

export function useBrowseInternshipPostings() {
  return useQuery({
    queryKey: ["internships", "postings", "browse"],
    queryFn: () => internshipsApi.browsePostings(),
  });
}

export function useMyInternshipApplications() {
  return useQuery({
    queryKey: ["internships", "applications", "me"],
    queryFn: () => internshipsApi.myApplications(),
  });
}

export function useMyInternships() {
  return useQuery({
    queryKey: ["internships", "me"],
    queryFn: () => internshipsApi.myInternships(),
  });
}

export function useApplyToInternship() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ postingId, coverLetter }: { postingId: string; coverLetter?: string }) =>
      internshipsApi.apply(postingId, coverLetter),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["internships", "applications", "me"] });
    },
  });
}

export function useWithdrawInternshipApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) => internshipsApi.withdraw(applicationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["internships", "applications", "me"] });
    },
  });
}
