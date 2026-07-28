import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ticketsApi, type CreateTicketPayload } from "@/features/tickets/api/tickets-api";

export function useMyTickets() {
  return useQuery({
    queryKey: ["tickets", "me"],
    queryFn: () => ticketsApi.myTickets(),
  });
}

export function useMyTicket(ticketId: string | undefined) {
  return useQuery({
    queryKey: ["tickets", "me", ticketId],
    queryFn: () => ticketsApi.getTicket(ticketId as string),
    enabled: !!ticketId,
  });
}

export function useCreateTicket() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateTicketPayload) => ticketsApi.createTicket(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tickets", "me"] });
    },
  });
}

export function useTicketComments(ticketId: string | undefined) {
  return useQuery({
    queryKey: ["tickets", "me", ticketId, "comments"],
    queryFn: () => ticketsApi.listComments(ticketId as string),
    enabled: !!ticketId,
  });
}

export function useAddComment(ticketId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (commentText: string) => ticketsApi.addComment(ticketId, commentText),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tickets", "me", ticketId, "comments"] });
    },
  });
}
