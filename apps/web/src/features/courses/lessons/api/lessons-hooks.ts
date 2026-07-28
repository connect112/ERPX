import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type LessonCreatePayload,
  type LessonUpdatePayload,
  lessonsApi,
} from "@/features/courses/lessons/api/lessons-api";

const lessonsKey = (courseId: string, chapterId: string) =>
  ["courses", "courses", courseId, "chapters", chapterId, "lessons"] as const;

export function useLessons(courseId: string, chapterId: string) {
  return useQuery({
    queryKey: lessonsKey(courseId, chapterId),
    queryFn: () => lessonsApi.list(courseId, chapterId),
    enabled: !!courseId && !!chapterId,
  });
}

export function useCreateLesson(courseId: string, chapterId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LessonCreatePayload) => lessonsApi.create(courseId, chapterId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: lessonsKey(courseId, chapterId) }),
  });
}

export function useUpdateLesson(courseId: string, chapterId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ lessonId, payload }: { lessonId: string; payload: LessonUpdatePayload }) =>
      lessonsApi.update(courseId, chapterId, lessonId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: lessonsKey(courseId, chapterId) }),
  });
}

export function useDeleteLesson(courseId: string, chapterId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (lessonId: string) => lessonsApi.remove(courseId, chapterId, lessonId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: lessonsKey(courseId, chapterId) }),
  });
}
