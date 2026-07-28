import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ClassroomCreatePayload,
  type ClassroomUpdatePayload,
  classroomsApi,
} from "@/features/classrooms/api/classrooms-api";

const classroomsKeys = {
  all: ["classrooms"] as const,
  list: (params: { skip?: number; limit?: number }) => [...classroomsKeys.all, "list", params] as const,
};

export function useClassroomsList(params: { skip?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: classroomsKeys.list(params),
    queryFn: () => classroomsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCreateClassroom() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ClassroomCreatePayload) => classroomsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: classroomsKeys.all }),
  });
}

export function useUpdateClassroom(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ClassroomUpdatePayload) => classroomsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: classroomsKeys.all }),
  });
}

export function useDeleteClassroom() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => classroomsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: classroomsKeys.all }),
  });
}
