import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { myBatchesApi } from "@/features/trainer-self-service/api/batches-api";

export function useMyBatches() {
  return useQuery({
    queryKey: ["batches", "me"],
    queryFn: () => myBatchesApi.myBatches(),
  });
}

export function useMyCourseAssignments(courseId: string | undefined) {
  return useQuery({
    queryKey: ["assignments", "me", courseId],
    queryFn: () => myBatchesApi.listAssignments(courseId as string),
    enabled: !!courseId,
  });
}

export function useMySubmissions(courseId: string | undefined, assignmentId: string | undefined) {
  return useQuery({
    queryKey: ["submissions", "me", courseId, assignmentId],
    queryFn: () => myBatchesApi.listSubmissions(courseId as string, assignmentId as string),
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
    }) => myBatchesApi.gradeSubmission(courseId, assignmentId, submissionId, { score, feedback }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["submissions", "me", courseId, assignmentId] });
    },
  });
}
