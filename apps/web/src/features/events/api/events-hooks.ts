import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type EventCreatePayload,
  type EventListParams,
  eventsApi,
} from "@/features/events/api/events-api";

const eventsKeys = {
  all: ["events"] as const,
  list: (params: EventListParams) => [...eventsKeys.all, "list", params] as const,
};

export function useEventsList(params: EventListParams) {
  return useQuery({
    queryKey: eventsKeys.list(params),
    queryFn: () => eventsApi.list(params),
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EventCreatePayload) => eventsApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: eventsKeys.all }),
  });
}

export function useDeleteEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => eventsApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: eventsKeys.all }),
  });
}
