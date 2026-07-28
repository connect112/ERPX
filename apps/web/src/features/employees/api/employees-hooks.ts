import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type EmployeeCreatePayload,
  type EmployeeListParams,
  type EmployeeUpdatePayload,
  employeesApi,
} from "@/features/employees/api/employees-api";
import type { EmploymentStatus } from "@/features/employees/schemas/employee-schemas";

const employeesKeys = {
  all: ["employees"] as const,
  list: (params: EmployeeListParams) => [...employeesKeys.all, "list", params] as const,
  detail: (id: string) => [...employeesKeys.all, "detail", id] as const,
};

export function useEmployeesList(params: EmployeeListParams) {
  return useQuery({
    queryKey: employeesKeys.list(params),
    queryFn: () => employeesApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useEmployee(id: string | undefined) {
  return useQuery({
    queryKey: employeesKeys.detail(id ?? ""),
    queryFn: () => employeesApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EmployeeCreatePayload) => employeesApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: employeesKeys.all }),
  });
}

export function useUpdateEmployee(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EmployeeUpdatePayload) => employeesApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: employeesKeys.all }),
  });
}

export function useChangeEmployeeStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ status, dateOfExit }: { status: EmploymentStatus; dateOfExit?: string }) =>
      employeesApi.changeStatus(id, status, dateOfExit),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: employeesKeys.all }),
  });
}

export function useDeleteEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => employeesApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: employeesKeys.all }),
  });
}
