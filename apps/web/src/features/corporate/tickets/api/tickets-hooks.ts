import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type TicketCommentCreatePayload,
  type TicketCreatePayload,
  type TicketListParams,
  type TicketUpdatePayload,
  ticketsApi,
} from "@/features/corporate/tickets/api/tickets-api";
import type { TicketStatus } from "@/features/corporate/tickets/schemas/ticket-schemas";

const ticketsKeys = {
  all: ["corporate", "tickets"] as const,
  list: (params: TicketListParams) => [...ticketsKeys.all, "list", params] as const,
  comments: (id: string) => [...ticketsKeys.all, id, "comments"] as const,
};

export function useTicketsList(params: TicketListParams) {
  return useQuery({
    queryKey: ticketsKeys.list(params),
    queryFn: () => ticketsApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useOverdueTickets() {
  return useQuery({
    queryKey: [...ticketsKeys.all, "overdue"],
    queryFn: () => ticketsApi.listOverdue(),
  });
}

export function useTicketComments(id: string | undefined) {
  return useQuery({
    queryKey: ticketsKeys.comments(id ?? ""),
    queryFn: () => ticketsApi.listComments(id as string, true),
    enabled: !!id,
  });
}

export function useCreateTicket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TicketCreatePayload) => ticketsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ticketsKeys.all }),
  });
}

export function useUpdateTicket(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TicketUpdatePayload) => ticketsApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ticketsKeys.all }),
  });
}

export function useChangeTicketStatus(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (status: TicketStatus) => ticketsApi.changeStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ticketsKeys.all }),
  });
}

export function useAddTicketComment(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TicketCommentCreatePayload) => ticketsApi.addComment(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ticketsKeys.comments(id) }),
  });
}
