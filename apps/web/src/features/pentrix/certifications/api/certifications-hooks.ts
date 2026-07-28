import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { certificationsApi } from "@/features/pentrix/certifications/api/certifications-api";

const certificationsKey = (studentId: string) => ["pentrix", "certifications", studentId] as const;

export function useCertificationsForStudent(studentId: string) {
  return useQuery({
    queryKey: certificationsKey(studentId),
    queryFn: () => certificationsApi.listForStudent(studentId),
    enabled: !!studentId,
  });
}

export function useIssueCertification(studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      trackName,
      minimumPoints,
      force,
    }: {
      trackName: string;
      minimumPoints: number;
      force?: boolean;
    }) => certificationsApi.issue(studentId, trackName, minimumPoints, force),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: certificationsKey(studentId) }),
  });
}
