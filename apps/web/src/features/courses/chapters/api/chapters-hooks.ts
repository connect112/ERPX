import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ChapterCreatePayload,
  type ChapterUpdatePayload,
  chaptersApi,
} from "@/features/courses/chapters/api/chapters-api";

const chaptersKey = (courseId: string) => ["courses", "courses", courseId, "chapters"] as const;

export function useChapters(courseId: string) {
  return useQuery({
    queryKey: chaptersKey(courseId),
    queryFn: () => chaptersApi.list(courseId),
    enabled: !!courseId,
  });
}

export function useCreateChapter(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ChapterCreatePayload) => chaptersApi.create(courseId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chaptersKey(courseId) }),
  });
}

export function useUpdateChapter(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ chapterId, payload }: { chapterId: string; payload: ChapterUpdatePayload }) =>
      chaptersApi.update(courseId, chapterId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chaptersKey(courseId) }),
  });
}

export function useDeleteChapter(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (chapterId: string) => chaptersApi.remove(courseId, chapterId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chaptersKey(courseId) }),
  });
}
