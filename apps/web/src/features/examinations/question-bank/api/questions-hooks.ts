import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type QuestionCreatePayload,
  type QuestionUpdatePayload,
  questionsApi,
} from "@/features/examinations/question-bank/api/questions-api";

const questionsKey = (courseId?: string) => ["examinations", "question-bank", courseId ?? "all"] as const;

export function useQuestions(courseId?: string) {
  return useQuery({
    queryKey: questionsKey(courseId),
    queryFn: () => questionsApi.list(courseId),
  });
}

export function useCreateQuestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: QuestionCreatePayload) => questionsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["examinations", "question-bank"] }),
  });
}

export function useUpdateQuestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: QuestionUpdatePayload }) =>
      questionsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["examinations", "question-bank"] }),
  });
}

export function useDeleteQuestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => questionsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["examinations", "question-bank"] }),
  });
}
