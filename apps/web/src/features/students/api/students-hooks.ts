import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type StudentCreatePayload,
  type StudentFromAdmissionPayload,
  type StudentListParams,
  type StudentUpdatePayload,
  studentsApi,
} from "@/features/students/api/students-api";
import type { StudentStatus } from "@/features/students/schemas/student-schemas";

const studentsKeys = {
  all: ["students"] as const,
  list: (params: StudentListParams) => [...studentsKeys.all, "list", params] as const,
  detail: (id: string) => [...studentsKeys.all, "detail", id] as const,
};

export function useStudentsList(params: StudentListParams) {
  return useQuery({
    queryKey: studentsKeys.list(params),
    queryFn: () => studentsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useStudent(id: string | undefined) {
  return useQuery({
    queryKey: studentsKeys.detail(id ?? ""),
    queryFn: () => studentsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StudentCreatePayload) => studentsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: studentsKeys.all }),
  });
}

export function useUpdateStudent(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StudentUpdatePayload) => studentsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: studentsKeys.all }),
  });
}

export function useChangeStudentStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ status, notes }: { status: StudentStatus; notes?: string }) =>
      studentsApi.changeStatus(id, status, notes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: studentsKeys.all }),
  });
}

export function useDeleteStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => studentsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: studentsKeys.all }),
  });
}

export function useCreateStudentFromAdmission() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      admissionId,
      payload,
    }: {
      admissionId: string;
      payload: StudentFromAdmissionPayload;
    }) => studentsApi.createFromAdmission(admissionId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: studentsKeys.all }),
  });
}
