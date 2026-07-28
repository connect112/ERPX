import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type CourseCreatePayload,
  type CourseListParams,
  type CourseUpdatePayload,
  coursesApi,
} from "@/features/courses/api/courses-api";

const coursesKeys = {
  all: ["courses", "courses"] as const,
  list: (params: CourseListParams) => [...coursesKeys.all, "list", params] as const,
  detail: (id: string) => [...coursesKeys.all, "detail", id] as const,
};

export function useCoursesList(params: CourseListParams) {
  return useQuery({
    queryKey: coursesKeys.list(params),
    queryFn: () => coursesApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCourse(id: string | undefined) {
  return useQuery({
    queryKey: coursesKeys.detail(id ?? ""),
    queryFn: () => coursesApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateCourse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CourseCreatePayload) => coursesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: coursesKeys.all }),
  });
}

export function useUpdateCourse(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CourseUpdatePayload) => coursesApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: coursesKeys.all }),
  });
}

export function useTogglePublishCourse(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (publish: boolean) => (publish ? coursesApi.publish(id) : coursesApi.unpublish(id)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: coursesKeys.all }),
  });
}

export function useDeleteCourse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => coursesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: coursesKeys.all }),
  });
}
