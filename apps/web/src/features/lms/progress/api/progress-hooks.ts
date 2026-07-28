import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { progressApi } from "@/features/lms/progress/api/progress-api";

const progressKey = (studentId: string, courseId: string) =>
  ["lms", "progress", studentId, courseId] as const;

export function useCourseProgress(studentId: string, courseId: string) {
  return useQuery({
    queryKey: progressKey(studentId, courseId),
    queryFn: () => progressApi.getCourseProgress(studentId, courseId),
    enabled: !!studentId && !!courseId,
  });
}

export function useToggleLessonProgress(studentId: string, courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ lessonId, complete }: { lessonId: string; complete: boolean }) =>
      complete
        ? progressApi.markComplete(studentId, lessonId)
        : progressApi.unmarkComplete(studentId, lessonId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: progressKey(studentId, courseId) }),
  });
}
