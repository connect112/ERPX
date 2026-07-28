import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type DepartmentCreatePayload,
  type DepartmentUpdatePayload,
  type DesignationCreatePayload,
  type DesignationUpdatePayload,
  hrApi,
} from "@/features/hr/api/hr-api";

const departmentsKey = ["hr", "departments"] as const;
const designationsKey = ["hr", "designations"] as const;

export function useDepartments(isActive?: boolean) {
  return useQuery({
    queryKey: [...departmentsKey, isActive],
    queryFn: () => hrApi.listDepartments(isActive),
  });
}

export function useCreateDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DepartmentCreatePayload) => hrApi.createDepartment(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: departmentsKey }),
  });
}

export function useUpdateDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: DepartmentUpdatePayload }) =>
      hrApi.updateDepartment(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: departmentsKey }),
  });
}

export function useDesignations(isActive?: boolean) {
  return useQuery({
    queryKey: [...designationsKey, isActive],
    queryFn: () => hrApi.listDesignations(isActive),
  });
}

export function useCreateDesignation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DesignationCreatePayload) => hrApi.createDesignation(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: designationsKey }),
  });
}

export function useUpdateDesignation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: DesignationUpdatePayload }) =>
      hrApi.updateDesignation(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: designationsKey }),
  });
}
