import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AchievementCreatePayload,
  achievementsApi,
} from "@/features/pentrix/achievements/api/achievements-api";

const achievementsKey = ["pentrix", "achievements"] as const;

export function useAchievements() {
  return useQuery({ queryKey: achievementsKey, queryFn: achievementsApi.list });
}

export function useStudentAchievements(studentId: string) {
  return useQuery({
    queryKey: ["pentrix", "achievements", "by-student", studentId],
    queryFn: () => achievementsApi.listForStudent(studentId),
    enabled: !!studentId,
  });
}

export function useCreateAchievement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AchievementCreatePayload) => achievementsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: achievementsKey }),
  });
}
