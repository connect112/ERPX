import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type HackathonCreatePayload,
  type HackathonListParams,
  type HackathonUpdatePayload,
  hackathonsApi,
} from "@/features/hackathons/api/hackathons-api";
import type { HackathonStatus } from "@/features/hackathons/schemas/hackathon-schemas";

const hackathonsKeys = {
  all: ["hackathons"] as const,
  list: (params: HackathonListParams) => [...hackathonsKeys.all, "list", params] as const,
  detail: (id: string) => [...hackathonsKeys.all, "detail", id] as const,
  teams: (id: string) => [...hackathonsKeys.all, id, "teams"] as const,
  submissions: (id: string) => [...hackathonsKeys.all, id, "submissions"] as const,
};

export function useHackathonsList(params: HackathonListParams) {
  return useQuery({
    queryKey: hackathonsKeys.list(params),
    queryFn: () => hackathonsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useHackathon(id: string | undefined) {
  return useQuery({
    queryKey: hackathonsKeys.detail(id ?? ""),
    queryFn: () => hackathonsApi.get(id as string),
    enabled: !!id,
  });
}

export function useHackathonTeams(id: string | undefined) {
  return useQuery({
    queryKey: hackathonsKeys.teams(id ?? ""),
    queryFn: () => hackathonsApi.listTeams(id as string),
    enabled: !!id,
  });
}

export function useHackathonSubmissions(id: string | undefined) {
  return useQuery({
    queryKey: hackathonsKeys.submissions(id ?? ""),
    queryFn: () => hackathonsApi.listSubmissions(id as string),
    enabled: !!id,
  });
}

export function useCreateHackathon() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: HackathonCreatePayload) => hackathonsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: hackathonsKeys.all }),
  });
}

export function useUpdateHackathon(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: HackathonUpdatePayload) => hackathonsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: hackathonsKeys.all }),
  });
}

export function useChangeHackathonStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (status: HackathonStatus) => hackathonsApi.changeStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: hackathonsKeys.all }),
  });
}

export function useGradeSubmission(hackathonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      submissionId,
      score,
      feedback,
    }: {
      submissionId: string;
      score: number;
      feedback?: string;
    }) => hackathonsApi.gradeSubmission(submissionId, score, feedback),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: hackathonsKeys.submissions(hackathonId) }),
  });
}
