import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { batchesApi } from "@/features/batches/api/batches-api";

export function useMyBatches() {
  return useQuery({
    queryKey: ["batches", "me"],
    queryFn: () => batchesApi.myBatches(),
  });
}

export function useMyCourseAssignments(courseId: string | undefined) {
  return useQuery({
    queryKey: ["assignments", "me", courseId],
    queryFn: () => batchesApi.listAssignments(courseId as string),
    enabled: !!courseId,
  });
}

export function useMySubmissions(courseId: string | undefined, assignmentId: string | undefined) {
  return useQuery({
    queryKey: ["submissions", "me", courseId, assignmentId],
    queryFn: () => batchesApi.listSubmissions(courseId as string, assignmentId as string),
    enabled: !!courseId && !!assignmentId,
  });
}

export function useGradeSubmission(courseId: string, assignmentId: string) {
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
    }) => batchesApi.gradeSubmission(courseId, assignmentId, submissionId, { score, feedback }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["submissions", "me", courseId, assignmentId] });
    },
  });
}
