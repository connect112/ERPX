import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type ProjectCreatePayload,
  type ProjectListParams,
  type ProjectUpdatePayload,
  projectsApi,
} from "@/features/corporate/projects/api/projects-api";
import type { ProjectStatus } from "@/features/corporate/projects/schemas/project-schemas";

const projectsKeys = {
  all: ["corporate", "projects"] as const,
  list: (params: ProjectListParams) => [...projectsKeys.all, "list", params] as const,
  detail: (id: string) => [...projectsKeys.all, "detail", id] as const,
};

export function useProjectsList(params: ProjectListParams) {
  return useQuery({
    queryKey: projectsKeys.list(params),
    queryFn: () => projectsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useProject(id: string | undefined) {
  return useQuery({
    queryKey: projectsKeys.detail(id ?? ""),
    queryFn: () => projectsApi.get(id as string),
    enabled: !!id,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProjectCreatePayload) => projectsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectsKeys.all }),
  });
}

export function useUpdateProject(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProjectUpdatePayload) => projectsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectsKeys.all }),
  });
}

export function useChangeProjectStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (status: ProjectStatus) => projectsApi.changeStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectsKeys.all }),
  });
}
