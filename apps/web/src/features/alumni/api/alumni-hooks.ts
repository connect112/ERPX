import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AlumniEventCreatePayload,
  type AlumniEventListParams,
  type AlumniEventUpdatePayload,
  alumniApi,
} from "@/features/alumni/api/alumni-api";
import type {
  EventStatus,
  ReferralStatus,
  RegistrationStatus,
} from "@/features/alumni/schemas/event-schemas";

const alumniKeys = {
  all: ["alumni"] as const,
  profiles: (params: { skip?: number; limit?: number }) => [...alumniKeys.all, "profiles", params] as const,
  events: (params: AlumniEventListParams) => [...alumniKeys.all, "events", params] as const,
  event: (id: string) => [...alumniKeys.all, "events", id] as const,
  registrations: (id: string) => [...alumniKeys.all, "events", id, "registrations"] as const,
  referrals: (params: { status?: ReferralStatus; skip?: number; limit?: number }) =>
    [...alumniKeys.all, "referrals", params] as const,
};

export function useProfilesList(params: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: alumniKeys.profiles(params),
    queryFn: () => alumniApi.listProfiles(params),
    placeholderData: keepPreviousData,
  });
}

export function useVerifyProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isVerified }: { id: string; isVerified: boolean }) =>
      alumniApi.verifyProfile(id, isVerified),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: alumniKeys.all }),
  });
}

export function useEventsList(params: AlumniEventListParams) {
  return useQuery({
    queryKey: alumniKeys.events(params),
    queryFn: () => alumniApi.listEvents(params),
    placeholderData: keepPreviousData,
  });
}

export function useEvent(id: string | undefined) {
  return useQuery({
    queryKey: alumniKeys.event(id ?? ""),
    queryFn: () => alumniApi.getEvent(id as string),
    enabled: !!id,
  });
}

export function useEventRegistrations(id: string | undefined) {
  return useQuery({
    queryKey: alumniKeys.registrations(id ?? ""),
    queryFn: () => alumniApi.listEventRegistrations(id as string),
    enabled: !!id,
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AlumniEventCreatePayload) => alumniApi.createEvent(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: alumniKeys.all }),
  });
}

export function useUpdateEvent(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AlumniEventUpdatePayload) => alumniApi.updateEvent(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: alumniKeys.all }),
  });
}

export function useChangeEventStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (status: EventStatus) => alumniApi.changeEventStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: alumniKeys.all }),
  });
}

export function useMarkAttendance(eventId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ registrationId, status }: { registrationId: string; status: RegistrationStatus }) =>
      alumniApi.markAttendance(registrationId, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: alumniKeys.registrations(eventId) }),
  });
}

export function useAllReferrals(params: { status?: ReferralStatus; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: alumniKeys.referrals(params),
    queryFn: () => alumniApi.listAllReferrals(params),
    placeholderData: keepPreviousData,
  });
}
