import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type EnquiryCreatePayload,
  type EnquiryUpdatePayload,
  enquiriesApi,
} from "@/features/crm/enquiries/api/enquiries-api";

const enquiriesKey = (leadId: string) => ["crm", "leads", leadId, "enquiries"] as const;

export function useEnquiries(leadId: string) {
  return useQuery({
    queryKey: enquiriesKey(leadId),
    queryFn: () => enquiriesApi.list(leadId),
    enabled: !!leadId,
  });
}

export function useCreateEnquiry(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EnquiryCreatePayload) => enquiriesApi.create(leadId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: enquiriesKey(leadId) }),
  });
}

export function useUpdateEnquiry(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ enquiryId, payload }: { enquiryId: string; payload: EnquiryUpdatePayload }) =>
      enquiriesApi.update(leadId, enquiryId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: enquiriesKey(leadId) }),
  });
}

export function useDeleteEnquiry(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (enquiryId: string) => enquiriesApi.remove(leadId, enquiryId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: enquiriesKey(leadId) }),
  });
}
