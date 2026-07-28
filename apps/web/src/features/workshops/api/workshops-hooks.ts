import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type RegistrationCreatePayload,
  type WorkshopCreatePayload,
  type WorkshopListParams,
  type WorkshopUpdatePayload,
  workshopsApi,
} from "@/features/workshops/api/workshops-api";
import type { WorkshopStatus } from "@/features/workshops/schemas/workshop-schemas";

const workshopsKeys = {
  all: ["workshops"] as const,
  list: (params: WorkshopListParams) => [...workshopsKeys.all, "list", params] as const,
  detail: (id: string) => [...workshopsKeys.all, "detail", id] as const,
  registrations: (id: string) => [...workshopsKeys.all, id, "registrations"] as const,
};

export function useWorkshopsList(params: WorkshopListParams) {
  return useQuery({
    queryKey: workshopsKeys.list(params),
    queryFn: () => workshopsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useWorkshop(id: string | undefined) {
  return useQuery({
    queryKey: workshopsKeys.detail(id ?? ""),
    queryFn: () => workshopsApi.get(id as string),
    enabled: !!id,
  });
}

export function useWorkshopRegistrations(id: string | undefined) {
  return useQuery({
    queryKey: workshopsKeys.registrations(id ?? ""),
    queryFn: () => workshopsApi.listRegistrations(id as string),
    enabled: !!id,
  });
}

export function useCreateWorkshop() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: WorkshopCreatePayload) => workshopsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workshopsKeys.all }),
  });
}

export function useUpdateWorkshop(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: WorkshopUpdatePayload) => workshopsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workshopsKeys.all }),
  });
}

export function useChangeWorkshopStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (status: WorkshopStatus) => workshopsApi.changeStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workshopsKeys.all }),
  });
}

export function useCreateRegistration(workshopId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RegistrationCreatePayload) =>
      workshopsApi.createRegistration(workshopId, payload),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: workshopsKeys.registrations(workshopId) }),
  });
}

export function useMarkAttendance(workshopId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ registrationId, attended }: { registrationId: string; attended: boolean }) =>
      workshopsApi.markAttendance(registrationId, attended),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: workshopsKeys.registrations(workshopId) }),
  });
}

export function useCancelRegistration(workshopId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (registrationId: string) => workshopsApi.cancelRegistration(registrationId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: workshopsKeys.registrations(workshopId) }),
  });
}
