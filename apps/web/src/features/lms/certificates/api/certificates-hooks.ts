import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { certificatesApi } from "@/features/lms/certificates/api/certificates-api";

const certificatesKey = (studentId: string) => ["lms", "certificates", studentId] as const;

export function useCertificatesForStudent(studentId: string) {
  return useQuery({
    queryKey: certificatesKey(studentId),
    queryFn: () => certificatesApi.listForStudent(studentId),
    enabled: !!studentId,
  });
}

export function useIssueCertificate(studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ courseId, force }: { courseId: string; force?: boolean }) =>
      certificatesApi.issue(studentId, courseId, force),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: certificatesKey(studentId) }),
  });
}
