import { useQuery } from "@tanstack/react-query";

import { transcriptsApi } from "@/features/transcripts/api/transcripts-api";

export function useMyTranscript() {
  return useQuery({
    queryKey: ["transcript", "me"],
    queryFn: () => transcriptsApi.myTranscript(),
  });
}
