import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ResourceCreatePayload,
  type ResourceUpdatePayload,
  resourcesApi,
} from "@/features/courses/resources/api/resources-api";

const resourcesKey = (courseId: string, chapterId: string, lessonId: string) =>
  ["courses", "courses", courseId, "chapters", chapterId, "lessons", lessonId, "resources"] as const;

export function useResources(courseId: string, chapterId: string, lessonId: string) {
  return useQuery({
    queryKey: resourcesKey(courseId, chapterId, lessonId),
    queryFn: () => resourcesApi.list(courseId, chapterId, lessonId),
    enabled: !!courseId && !!chapterId && !!lessonId,
  });
}

export function useCreateResource(courseId: string, chapterId: string, lessonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ResourceCreatePayload) =>
      resourcesApi.create(courseId, chapterId, lessonId, payload),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: resourcesKey(courseId, chapterId, lessonId) }),
  });
}

export function useUpdateResource(courseId: string, chapterId: string, lessonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      resourceId,
      payload,
    }: {
      resourceId: string;
      payload: ResourceUpdatePayload;
    }) => resourcesApi.update(courseId, chapterId, lessonId, resourceId, payload),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: resourcesKey(courseId, chapterId, lessonId) }),
  });
}

export function useDeleteResource(courseId: string, chapterId: string, lessonId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (resourceId: string) =>
      resourcesApi.remove(courseId, chapterId, lessonId, resourceId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: resourcesKey(courseId, chapterId, lessonId) }),
  });
}
