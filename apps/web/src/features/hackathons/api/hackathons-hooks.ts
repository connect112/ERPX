import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type HackathonCreatePayload,
  type HackathonListParams,
  type HackathonUpdatePayload,
  type MemberRef,
  type MemberUpdatePayload,
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
    // Teams form live while an event is on.
    refetchInterval: 15_000,
  });
}

/** Everyone invited to the hackathon, with contact details, team and sign-in status. */
export function useParticipants(id: string | undefined) {
  return useQuery({
    queryKey: [...hackathonsKeys.all, id ?? "", "participants"],
    queryFn: () => hackathonsApi.participants(id as string),
    enabled: !!id,
    refetchInterval: 20_000,
  });
}

export function useParticipantActions(hackathonId: string) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: [...hackathonsKeys.all, hackathonId] });
  return {
    remove: useMutation({
      mutationFn: ({ studentIds, deleteAccount }: { studentIds: string[]; deleteAccount: boolean }) =>
        hackathonsApi.removeParticipants(hackathonId, studentIds, deleteAccount),
      onSuccess: refresh,
    }),
    sendLinks: useMutation({
      mutationFn: (studentIds: string[] | null) => hackathonsApi.sendLoginLinks(hackathonId, studentIds),
    }),
  };
}

/** Every team with its members' contact details. */
export function useRoster(id: string | undefined) {
  return useQuery({
    queryKey: [...hackathonsKeys.all, id ?? "", "roster"],
    queryFn: () => hackathonsApi.roster(id as string),
    enabled: !!id,
    // Students form teams on their own while an event is on.
    refetchInterval: 15_000,
  });
}

/** People with a login who aren't in a team yet, matching what the organiser typed. */
export function useTeamCandidates(id: string, query: string, enabled: boolean) {
  return useQuery({
    queryKey: [...hackathonsKeys.all, id, "candidates", query],
    queryFn: () => hackathonsApi.candidates(id, query),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useTaskSubmissions(id: string | undefined) {
  return useQuery({
    queryKey: hackathonsKeys.submissions(id ?? ""),
    queryFn: () => hackathonsApi.listTaskSubmissions(id as string),
    enabled: !!id,
    // New submissions arrive while the event is on.
    refetchInterval: 15_000,
  });
}

/** The live ranking (also shown when it is hidden from participants). */
export function useStaffLeaderboard(id: string | undefined) {
  return useQuery({
    queryKey: [...hackathonsKeys.all, id ?? "", "leaderboard"],
    queryFn: () => hackathonsApi.leaderboard(id as string),
    enabled: !!id,
    refetchInterval: 10_000,
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

/** The organiser's team and member controls. Each refreshes the teams, roster, leaderboard and submissions. */
export function useTeamAdmin(hackathonId: string) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: [...hackathonsKeys.all, hackathonId] });
  const mutation = <TVars>(fn: (vars: TVars) => Promise<{ message: string }>) => ({
    mutationFn: fn,
    onSuccess: refresh,
  });
  return {
    createTeam: useMutation(
      mutation(({ name, member }: { name: string; member: MemberRef }) =>
        hackathonsApi.createTeam(hackathonId, name, member)
      )
    ),
    renameTeam: useMutation(
      mutation(({ teamId, name }: { teamId: string; name: string }) =>
        hackathonsApi.renameTeam(hackathonId, teamId, name)
      )
    ),
    deleteTeam: useMutation(mutation((teamId: string) => hackathonsApi.deleteTeam(hackathonId, teamId))),
    addMember: useMutation(
      mutation(({ teamId, member }: { teamId: string; member: MemberRef }) =>
        hackathonsApi.addMember(hackathonId, teamId, member)
      )
    ),
    removeMember: useMutation(
      mutation(({ teamId, studentId }: { teamId: string; studentId: string }) =>
        hackathonsApi.removeMember(hackathonId, teamId, studentId)
      )
    ),
    moveMember: useMutation(
      mutation(({ studentId, teamId }: { studentId: string; teamId: string }) =>
        hackathonsApi.moveMember(hackathonId, studentId, teamId)
      )
    ),
    updateMember: useMutation(
      mutation(({ studentId, payload }: { studentId: string; payload: MemberUpdatePayload }) =>
        hackathonsApi.updateMember(hackathonId, studentId, payload)
      )
    ),
    sendLoginLink: useMutation(mutation((studentId: string) => hackathonsApi.sendLoginLink(hackathonId, studentId))),
  };
}

export function useDeleteTaskSubmission(hackathonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (submissionId: string) => hackathonsApi.deleteTaskSubmission(hackathonId, submissionId),
    // Team totals and the leaderboard change with it.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...hackathonsKeys.all, hackathonId] }),
  });
}

export function useGradeTaskSubmission(hackathonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      submissionId,
      marks,
      feedback,
    }: {
      submissionId: string;
      marks: { score?: number; rubricScores?: Record<string, number> };
      feedback?: string;
    }) => hackathonsApi.gradeTaskSubmission(hackathonId, submissionId, marks, feedback),
    // The leaderboard and team totals are computed from these scores, so refresh them together.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [...hackathonsKeys.all, hackathonId] }),
  });
}
