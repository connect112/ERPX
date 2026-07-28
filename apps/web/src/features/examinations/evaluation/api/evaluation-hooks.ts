import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { evaluationApi } from "@/features/examinations/evaluation/api/evaluation-api";

const answersKey = (attemptId: string) => ["examinations", "evaluation", attemptId, "answers"] as const;

export function useStartExamAttempt(examId: string, onSettled?: () => void) {
  return useMutation({
    mutationFn: (studentId: string) => evaluationApi.startAttempt(examId, studentId),
    onSettled,
  });
}

export function useAnswers(attemptId: string) {
  return useQuery({
    queryKey: answersKey(attemptId),
    queryFn: () => evaluationApi.listAnswers(attemptId),
    enabled: !!attemptId,
  });
}

export function useSubmitAnswer(attemptId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ questionId, answerText }: { questionId: string; answerText?: string }) =>
      evaluationApi.submitAnswer(attemptId, questionId, answerText),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: answersKey(attemptId) }),
  });
}

export function useSubmitAttempt() {
  return useMutation({
    mutationFn: (attemptId: string) => evaluationApi.submitAttempt(attemptId),
  });
}

export function useGradeAnswer(attemptId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ answerId, marksAwarded }: { answerId: string; marksAwarded: number }) =>
      evaluationApi.gradeAnswer(answerId, marksAwarded),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: answersKey(attemptId) }),
  });
}

export function useFinalizeEvaluation() {
  return useMutation({
    mutationFn: (attemptId: string) => evaluationApi.finalizeEvaluation(attemptId),
  });
}
