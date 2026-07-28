import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { coursesApi } from "@/features/courses/api/courses-api";

export function useMyEnrollments() {
  return useQuery({
    queryKey: ["enrollments", "me"],
    queryFn: () => coursesApi.myEnrollments(),
  });
}

export function useMyCourse(courseId: string | undefined) {
  return useQuery({
    queryKey: ["courses", "me", courseId],
    queryFn: () => coursesApi.getCourse(courseId as string),
    enabled: !!courseId,
  });
}

export function useMyChapters(courseId: string | undefined) {
  return useQuery({
    queryKey: ["chapters", "me", courseId],
    queryFn: () => coursesApi.listChapters(courseId as string),
    enabled: !!courseId,
  });
}

export function useMyLessons(courseId: string | undefined, chapterId: string | undefined) {
  return useQuery({
    queryKey: ["lessons", "me", courseId, chapterId],
    queryFn: () => coursesApi.listLessons(courseId as string, chapterId as string),
    enabled: !!courseId && !!chapterId,
  });
}

export function useMyCourseProgress(courseId: string | undefined) {
  return useQuery({
    queryKey: ["progress", "me", courseId],
    queryFn: () => coursesApi.myProgress(courseId as string),
    enabled: !!courseId,
  });
}

export function useMarkLessonComplete(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (lessonId: string) => coursesApi.markLessonComplete(lessonId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["progress", "me", courseId] });
    },
  });
}
