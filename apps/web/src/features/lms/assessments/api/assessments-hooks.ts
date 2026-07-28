import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AssessmentCreatePayload,
  type AssessmentUpdatePayload,
  assessmentsApi,
} from "@/features/lms/assessments/api/assessments-api";

const assessmentsKey = (courseId: string) => ["lms", "assessments", courseId] as const;
const attemptsKey = (courseId: string, assessmentId: string) =>
  [...assessmentsKey(courseId), assessmentId, "attempts"] as const;

export function useAssessments(courseId: string) {
  return useQuery({
    queryKey: assessmentsKey(courseId),
    queryFn: () => assessmentsApi.list(courseId),
    enabled: !!courseId,
  });
}

export function useCreateAssessment(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssessmentCreatePayload) => assessmentsApi.create(courseId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assessmentsKey(courseId) }),
  });
}

export function useUpdateAssessment(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      assessmentId,
      payload,
    }: {
      assessmentId: string;
      payload: AssessmentUpdatePayload;
    }) => assessmentsApi.update(courseId, assessmentId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assessmentsKey(courseId) }),
  });
}

export function useDeleteAssessment(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assessmentId: string) => assessmentsApi.remove(courseId, assessmentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assessmentsKey(courseId) }),
  });
}

export function useAttempts(courseId: string, assessmentId: string) {
  return useQuery({
    queryKey: attemptsKey(courseId, assessmentId),
    queryFn: () => assessmentsApi.listAttempts(courseId, assessmentId),
    enabled: !!courseId && !!assessmentId,
  });
}

export function useStartAttempt(courseId: string, assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (studentId: string) => assessmentsApi.startAttempt(courseId, assessmentId, studentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: attemptsKey(courseId, assessmentId) }),
  });
}

export function useSubmitAttempt(courseId: string, assessmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ attemptId, score }: { attemptId: string; score: number }) =>
      assessmentsApi.submitAttempt(courseId, assessmentId, attemptId, score),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: attemptsKey(courseId, assessmentId) }),
  });
}
