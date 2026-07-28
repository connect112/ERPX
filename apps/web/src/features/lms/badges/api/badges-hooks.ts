import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { type BadgeCreatePayload, badgesApi } from "@/features/lms/badges/api/badges-api";

const badgesKey = ["lms", "badges"] as const;
const studentBadgesKey = (studentId: string) => ["lms", "badges", "by-student", studentId] as const;

export function useBadges() {
  return useQuery({ queryKey: badgesKey, queryFn: badgesApi.list });
}

export function useStudentBadges(studentId: string) {
  return useQuery({
    queryKey: studentBadgesKey(studentId),
    queryFn: () => badgesApi.listForStudent(studentId),
    enabled: !!studentId,
  });
}

export function useCreateBadge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BadgeCreatePayload) => badgesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: badgesKey }),
  });
}

export function useAwardBadge() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ studentId, badgeId }: { studentId: string; badgeId: string }) =>
      badgesApi.award(studentId, badgeId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: studentBadgesKey(variables.studentId) });
    },
  });
}
