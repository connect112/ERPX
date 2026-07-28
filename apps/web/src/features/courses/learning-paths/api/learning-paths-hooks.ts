import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AddCourseToPathPayload,
  type LearningPathCreatePayload,
  type LearningPathUpdatePayload,
  learningPathsApi,
} from "@/features/courses/learning-paths/api/learning-paths-api";

const pathsKey = ["courses", "learning-paths"] as const;
const pathDetailKey = (id: string) => [...pathsKey, "detail", id] as const;
const pathCoursesKey = (id: string) => [...pathsKey, id, "courses"] as const;

export function useLearningPaths() {
  return useQuery({ queryKey: pathsKey, queryFn: learningPathsApi.list });
}

export function useLearningPath(id: string | undefined) {
  return useQuery({
    queryKey: pathDetailKey(id ?? ""),
    queryFn: () => learningPathsApi.get(id as string),
    enabled: !!id,
  });
}

export function usePathCourses(id: string) {
  return useQuery({
    queryKey: pathCoursesKey(id),
    queryFn: () => learningPathsApi.listCourses(id),
    enabled: !!id,
  });
}

export function useCreateLearningPath() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LearningPathCreatePayload) => learningPathsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: pathsKey }),
  });
}

export function useUpdateLearningPath(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LearningPathUpdatePayload) => learningPathsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: pathsKey }),
  });
}

export function useDeleteLearningPath() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => learningPathsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: pathsKey }),
  });
}

export function useAddCourseToPath(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AddCourseToPathPayload) => learningPathsApi.addCourse(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: pathCoursesKey(id) }),
  });
}

export function useRemoveCourseFromPath(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (courseId: string) => learningPathsApi.removeCourse(id, courseId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: pathCoursesKey(id) }),
  });
}
