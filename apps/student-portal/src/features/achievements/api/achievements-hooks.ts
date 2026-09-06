import { useQuery } from "@tanstack/react-query";

import { achievementsApi } from "@/features/achievements/api/achievements-api";

export function useAchievementCatalog() {
  return useQuery({
    queryKey: ["pentrix", "achievements", "catalog"],
    queryFn: () => achievementsApi.catalog(),
  });
}

export function useMyAchievements(studentId: string | undefined) {
  return useQuery({
    queryKey: ["pentrix", "achievements", "me", studentId],
    queryFn: () => achievementsApi.mine(studentId as string),
    enabled: Boolean(studentId),
  });
}

export function useMyCertifications(studentId: string | undefined) {
  return useQuery({
    queryKey: ["pentrix", "certifications", "me", studentId],
    queryFn: () => achievementsApi.myCertifications(studentId as string),
    enabled: Boolean(studentId),
  });
}
