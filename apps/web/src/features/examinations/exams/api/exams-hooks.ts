import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ExamCreatePayload,
  type ExamUpdatePayload,
  examsApi,
} from "@/features/examinations/exams/api/exams-api";

const examsKey = (courseId: string) => ["examinations", "exams", courseId] as const;
const examQuestionsKey = (courseId: string, examId: string) =>
  [...examsKey(courseId), examId, "questions"] as const;

export function useExams(courseId: string) {
  return useQuery({
    queryKey: examsKey(courseId),
    queryFn: () => examsApi.list(courseId),
    enabled: !!courseId,
  });
}

export function useCreateExam(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ExamCreatePayload) => examsApi.create(courseId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: examsKey(courseId) }),
  });
}

export function useUpdateExam(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ examId, payload }: { examId: string; payload: ExamUpdatePayload }) =>
      examsApi.update(courseId, examId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: examsKey(courseId) }),
  });
}

export function useDeleteExam(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (examId: string) => examsApi.remove(courseId, examId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: examsKey(courseId) }),
  });
}

export function useExamQuestions(courseId: string, examId: string) {
  return useQuery({
    queryKey: examQuestionsKey(courseId, examId),
    queryFn: () => examsApi.listQuestions(courseId, examId),
    enabled: !!courseId && !!examId,
  });
}

export function useAddQuestionToExam(courseId: string, examId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { question_id: string; marks_allocated: number; order_index: number }) =>
      examsApi.addQuestion(courseId, examId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: examQuestionsKey(courseId, examId) }),
  });
}

export function useRemoveQuestionFromExam(courseId: string, examId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (questionId: string) => examsApi.removeQuestion(courseId, examId, questionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: examQuestionsKey(courseId, examId) }),
  });
}
