import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { liveClassesApi, type LiveClassStatus } from "@/features/live-classes/api/live-classes-api";

const liveClassesKey = ["live-classes", "trainer", "me"] as const;

export function useMyLiveClasses() {
  return useQuery({
    queryKey: liveClassesKey,
    queryFn: () => liveClassesApi.myLiveClasses(),
  });
}

export function useChangeLiveClassStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
      recordingUrl,
    }: {
      id: string;
      status: LiveClassStatus;
      recordingUrl?: string;
    }) => liveClassesApi.changeStatus(id, { status, recording_url: recordingUrl }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: liveClassesKey }),
  });
}
